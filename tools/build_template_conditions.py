# -*- coding: utf-8 -*-
r"""把「模板」和「它被观测到时用的条件」对上，产出可查的条件包络。

数据：reports/ord_condition_dataset/*.parquet（ORD 带条件记录，含原子映射）。
做法：对每条记录用 rdchiral 抽模板（与挖矿同一函数），把条件累加到该模板名下。

输出：reports/template_conditions.json
  { "template": {"n": int, "t_min": float, "t_max": float,
                 "t_hist": [14 个 25°C 区间的计数，起点 -50 °C],
                 "tm_min": float, "tm_max": float,
                 "tm_hist": [12 个对数区间计数，0.5 分钟到 40 小时],
                 "solv": {"water": n, ...}, "cat": n_with_catalyst,
                 "yield_med": float|null } }

用法: python tools\build_template_conditions.py [max_files=40] [workers=4]
"""
from __future__ import annotations

import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
if str(STAGE / "libs") not in sys.path:
    sys.path.insert(0, str(STAGE / "libs"))
if str(STAGE) not in sys.path:
    sys.path.insert(0, str(STAGE))
SRC = STAGE / "reports" / "ord_condition_dataset"
OUT = STAGE / "reports" / "template_conditions.json"

T_BIN = 25.0
T_ORIGIN = -50.0
T_NBIN = 14
TM_MIN, TM_MAX, TM_NBIN = 0.5, 1440.0, 12
_SINK = None


def _t_bin(t: float) -> int:
    i = int((t - T_ORIGIN) // T_BIN)
    return max(0, min(T_NBIN - 1, i))


def _tm_bin(t: float) -> int:
    t = max(TM_MIN, min(TM_MAX, t))
    frac = math.log(t / TM_MIN) / math.log(TM_MAX / TM_MIN)
    return max(0, min(TM_NBIN - 1, int(frac * TM_NBIN)))


def _extract_one(row: Dict[str, Any]) -> Dict[str, Any] | None:
    """返回 {template, t, tm, solv, cat, yield} 或 None。"""
    import rdchiral.template_extractor as te

    global _SINK
    rx = row.get("reactants")
    pr = row.get("product")
    if not rx or not pr or ":" not in str(pr):
        return None
    if _SINK is None:
        _SINK = open(os.devnull, "w")
    old = os.dup(1)
    try:
        os.dup2(_SINK.fileno(), 1)
        t = te.extract_from_reaction(
            {"reactants": str(rx), "products": str(pr), "_id": "x"})
    except Exception:
        t = None
    finally:
        sys.stdout.flush()
        os.dup2(old, 1)
        os.close(old)
    if not t:
        return None
    tpl = t.get("reaction_smarts")
    if not tpl or ">>" not in tpl:
        return None
    return {"template": tpl, "t": row.get("temperature_C"),
            "tm": row.get("reaction_time_min"),
            "solv": row.get("solvent_names"), "cat": row.get("catalyst_names"),
            "yld": row.get("yield_percent")}


def _worker(paths):
    import pyarrow.parquet as pq

    acc: Dict[str, Dict[str, Any]] = {}
    n_rows = n_used = 0
    for p in paths:
        tb = pq.ParquetFile(p)
        cols = ["reactants", "product", "temperature_C", "reaction_time_min",
                "solvent_names", "catalyst_names", "yield_percent"]
        df = tb.read(columns=cols).to_pandas()
        for rec in df.to_dict("records"):
            n_rows += 1
            got = _extract_one(rec)
            if not got:
                continue
            n_used += 1
            e = acc.setdefault(got["template"], {
                "n": 0, "t_min": None, "t_max": None,
                "t_hist": [0] * T_NBIN, "tm_min": None, "tm_max": None,
                "tm_hist": [0] * TM_NBIN, "solv": {}, "cat": 0,
                "yld_sum": 0.0, "yld_n": 0})
            e["n"] += 1
            if got["t"] is not None and str(got["t"]) != "nan":
                tv = float(got["t"])
                e["t_min"] = tv if e["t_min"] is None else min(e["t_min"], tv)
                e["t_max"] = tv if e["t_max"] is None else max(e["t_max"], tv)
                e["t_hist"][_t_bin(tv)] += 1
            if got["tm"] is not None and str(got["tm"]) != "nan":
                mv = float(got["tm"])
                if mv > 0:
                    e["tm_min"] = mv if e["tm_min"] is None else min(e["tm_min"], mv)
                    e["tm_max"] = mv if e["tm_max"] is None else max(e["tm_max"], mv)
                    e["tm_hist"][_tm_bin(mv)] += 1
            sv = got["solv"]
            if sv is not None and str(sv) != "nan":
                for s in str(sv).split(";"):
                    s = s.strip().lower()
                    if s:
                        e["solv"][s] = e["solv"].get(s, 0) + 1
            cv = got["cat"]
            if cv is not None and str(cv) != "nan" and str(cv).strip():
                e["cat"] += 1
            yv = got["yld"]
            if yv is not None and str(yv) != "nan":
                e["yld_sum"] += float(yv)
                e["yld_n"] += 1
    return acc, n_rows, n_used


def main() -> int:
    max_files = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    files = sorted(SRC.glob("*.parquet"))[:max_files]
    if not files:
        print("没有找到 parquet")
        return 1
    print(f"文件 {len(files)} 个，workers={workers}", flush=True)
    chunks = [files[i::workers] for i in range(workers)]
    total: Dict[str, Dict[str, Any]] = {}
    n_rows = n_used = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_worker, c) for c in chunks if c]
        for i, f in enumerate(as_completed(futs), 1):
            acc, nr, nu = f.result()
            n_rows += nr
            n_used += nu
            for k, v in acc.items():
                e = total.setdefault(k, {
                    "n": 0, "t_min": None, "t_max": None,
                    "t_hist": [0] * T_NBIN, "tm_min": None, "tm_max": None,
                    "tm_hist": [0] * TM_NBIN, "solv": {}, "cat": 0,
                    "yld_sum": 0.0, "yld_n": 0})
                e["n"] += v["n"]
                for f2 in ("t_min", "t_max", "tm_min", "tm_max"):
                    if v[f2] is not None:
                        if e[f2] is None:
                            e[f2] = v[f2]
                        elif f2.endswith("min"):
                            e[f2] = min(e[f2], v[f2])
                        else:
                            e[f2] = max(e[f2], v[f2])
                for j in range(T_NBIN):
                    e["t_hist"][j] += v["t_hist"][j]
                for j in range(TM_NBIN):
                    e["tm_hist"][j] += v["tm_hist"][j]
                for s, c in v["solv"].items():
                    e["solv"][s] = e["solv"].get(s, 0) + c
                e["cat"] += v["cat"]
                e["yld_sum"] += v["yld_sum"]
                e["yld_n"] += v["yld_n"]
            print(f"  {i}/{len(futs)} 合并完成：模板 {len(total)}", flush=True)

    out = {}
    for k, e in total.items():
        e.pop("yld_sum", None)
        yn = e.pop("yld_n", 0)
        e["yield_med"] = None
        if yn:
            e["yield_med"] = round(e.get("yld_sum", 0) / yn, 1)
        e.pop("yld_sum", None)
        out[k] = e
    OUT.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"记录 {n_rows} · 抽出模板 {n_used} · 唯一模板 {len(out)} · "
          f"输出 {OUT} ({OUT.stat().st_size/1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
