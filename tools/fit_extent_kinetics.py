# -*- coding: utf-8 -*-
"""从文献实测的「时间 → 转化率」数据拟合热降解动力学，并换算成 extent 层用的 Q10。

为什么需要这个
--------------
`conditions/kinetics.json` 里的 `q10 = 2.0` 是教科书经验值（AGENTS §十二要求标
`unvalidated_model_choice`）。要让条件层真正参与产物生成，必须先用实测数据把它标定出来。

本脚本只做两件事：
1. 对每组 (T, t, 转化率) 拟合一级反应 `1-y = exp(-k t)`，给出 k、R²、半衰期；
2. 跨温度用 `Q10 = (k2/k1)^(10/(T2-T1))` 估计 Q10，并与当前参数对照。

输入格式（`conditions/kinetics_measurements.json`）
---------------------------------------------------
{
  "schema": "chemreact-kinetics-measurements/1",
  "datasets": [
    {"id": "ginsenoside_rb1_100c",
     "reaction": "hydrolysis_glycoside",
     "temp_C": 100,
     "times_min": [0, 15, 30, 60, 120],
     "conversion": [0.0, 0.12, 0.24, 0.45, 0.72],
     "source": {"title": "...", "doi": "...", "figure_or_table": "Table 2",
                "quote": "..."}}
  ]
}

用法
----
    python -I tools/fit_extent_kinetics.py --selftest          # 用合成数据验证拟合器
    python -I tools/fit_extent_kinetics.py                     # 拟合实测数据
    python -I tools/fit_extent_kinetics.py --out reports/xxx.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
MEAS = ROOT / "conditions" / "kinetics_measurements.json"
KIN = ROOT / "conditions" / "kinetics.json"

# Windows 控制台默认 GBK，打印 °C / R² 会崩（AGENTS §七：脚本要自己能跑）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                      # noqa: BLE001
        pass


def fit_first_order(times: List[float], conv: List[float]) -> Dict:
    """拟合 y = 1 - exp(-k t)；用最小二乘解 k。返回 k / R² / 半衰期。"""
    xs, ys = [], []
    for t, y in zip(times, conv):
        if t <= 0:
            continue
        if not (0.0 < y < 1.0):
            continue
        xs.append(t)
        ys.append(-math.log(1.0 - y))
    n = len(xs)
    if n < 2:
        return {"k_per_min": None, "n_points": n,
                "note": "有效点少于 2 个，无法定 k"}
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    k = sxy / sxx
    # R²（过原点回归）
    ybar = sum(ys) / n
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    ss_res = sum((y - k * x) ** 2 for x, y in zip(xs, ys))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {"k_per_min": k, "n_points": n, "r2": r2,
            "half_life_min": (math.log(2.0) / k) if k > 0 else None}


def q10_between(k1: float, t1: float, k2: float, t2: float) -> Optional[float]:
    if k1 <= 0 or k2 <= 0 or abs(t2 - t1) < 1e-9:
        return None
    return (k2 / k1) ** (10.0 / (t2 - t1))


def activation_energy(k_pairs: List[Tuple[float, float]]) -> Optional[Dict]:
    """Arrhenius：ln k = ln A - Ea/(R T)。k_pairs = [(T_K, k), ...]"""
    pts = [(t, math.log(k)) for t, k in k_pairs if k > 0]
    n = len(pts)
    if n < 2:
        return None
    R = 8.314462618  # J/(mol·K)
    sx = sum(1.0 / t for t, _ in pts)
    sy = sum(y for _, y in pts)
    sxx = sum((1.0 / t) ** 2 for t, _ in pts)
    sxy = sum((1.0 / t) * y for t, y in pts)
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-18:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return {"ea_kJ_per_mol": -slope * R / 1000.0,
            "ln_A": intercept, "n_points": n}


def load_measurements(path: Path) -> List[Dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("datasets") or [])


def analyse(datasets: List[Dict]) -> Dict:
    out = {"schema": "chemreact-kinetics-calibration/1",
           "current_params": {}, "datasets": [], "by_reaction": {}}
    try:
        kin = json.loads(KIN.read_text(encoding="utf-8"))
        out["current_params"] = {"q10": kin.get("q10"),
                                 "validation": kin.get("validation")}
    except Exception as ex:                       # noqa: BLE001
        out["current_params"] = {"error": "%s: %s" % (type(ex).__name__, ex)}

    for ds in datasets:
        # 两种数据形态：① 时间-转化率曲线（自己拟合）② 文献已给出的速率常数（直接引用）
        # ② 绝不能反推成假的时间序列——那等于把自己的假设当成实验数据（AGENTS §十二）。
        k_rep = ds.get("k_per_h")
        if k_rep:
            k_min = float(k_rep) / 60.0
            rec = {"id": ds.get("id"), "reaction": ds.get("reaction"),
                   "temp_C": ds.get("temp_C"), "n_points": None,
                   "k_per_min": k_min, "k_per_h_reported": float(k_rep),
                   "r2": None, "half_life_min": (math.log(2.0) / k_min) if k_min > 0 else None,
                   "source": ds.get("source"), "origin": "reported_rate_constant",
                   "note": "文献直接报告的 k，未经本脚本拟合"}
        else:
            fit = fit_first_order(ds.get("times_min") or [], ds.get("conversion") or [])
            rec = {"id": ds.get("id"), "reaction": ds.get("reaction"),
                   "temp_C": ds.get("temp_C"), "n_points": fit.get("n_points"),
                   "k_per_min": fit.get("k_per_min"), "r2": fit.get("r2"),
                   "half_life_min": fit.get("half_life_min"),
                   "source": ds.get("source"), "origin": "fitted_time_course",
                   "note": fit.get("note", "")}
        out["datasets"].append(rec)

    groups: Dict[str, List[Dict]] = {}
    for rec in out["datasets"]:
        if rec.get("k_per_min"):
            groups.setdefault(str(rec.get("reaction") or "?"), []).append(rec)

    for rxn, recs in groups.items():
        recs = sorted(recs, key=lambda r: r["temp_C"])
        q10s = []
        for a, b in zip(recs, recs[1:]):
            q = q10_between(a["k_per_min"], a["temp_C"], b["k_per_min"], b["temp_C"])
            if q:
                q10s.append({"from_C": a["temp_C"], "to_C": b["temp_C"],
                             "q10": q})
        ea = activation_energy([(r["temp_C"] + 273.15, r["k_per_min"]) for r in recs])
        q10_mean = (sum(q["q10"] for q in q10s) / len(q10s)) if q10s else None
        cur = None
        try:
            cur = float((out["current_params"].get("q10") or {}).get("value"))
        except Exception:                          # noqa: BLE001
            cur = None
        out["by_reaction"][rxn] = {
            "temperatures_C": [r["temp_C"] for r in recs],
            "k_per_min": [r["k_per_min"] for r in recs],
            "q10_pairs": q10s,
            "q10_mean": q10_mean,
            "q10_current": cur,
            "q10_delta": (q10_mean - cur) if (q10_mean is not None and cur is not None) else None,
            "arrhenius": ea,
        }
    return out


def selftest() -> int:
    """用已知 q10=2、k(100°C)=0.01 的合成数据验证拟合器。"""
    fails = 0

    def check(cond, msg):
        nonlocal fails
        print(("  PASS  " if cond else "  FAIL  ") + msg)
        if not cond:
            fails += 1

    times = [0, 15, 30, 60, 120, 240]
    data = []
    for T in (80, 90, 100):
        k = 0.01 * (2.0 ** ((T - 100) / 10.0))
        data.append({"id": "syn_%d" % T, "reaction": "syn", "temp_C": T,
                     "times_min": times,
                     "conversion": [1 - math.exp(-k * t) for t in times]})
    res = analyse(data)
    ks = {r["temp_C"]: r["k_per_min"] for r in res["datasets"]}
    check(abs(ks[100] - 0.01) < 1e-6, "k(100°C) 还原=%.6f" % ks[100])
    check(abs(ks[80] - 0.0025) < 1e-6, "k(80°C) 还原=%.6f" % ks[80])
    syn = res["by_reaction"]["syn"]
    check(syn["q10_mean"] is not None and abs(syn["q10_mean"] - 2.0) < 1e-6,
          "Q10 还原=%.4f" % (syn["q10_mean"] or -1))
    check(all(abs(d["r2"] - 1.0) < 1e-6 for d in res["datasets"]), "R²=1（无噪声）")
    check(syn["arrhenius"] is not None and syn["arrhenius"]["ea_kJ_per_mol"] > 0,
          "Arrhenius Ea=%.1f kJ/mol" % (syn["arrhenius"]["ea_kJ_per_mol"]
                                        if syn["arrhenius"] else -1))
    # 两点数据应该拒绝拟合
    two = analyse([{"id": "two", "reaction": "x", "temp_C": 100,
                    "times_min": [0, 60], "conversion": [0.0, 0.5]}])
    check(two["datasets"][0]["k_per_min"] is None, "两点数据不明算 k")
    print("SELFTEST %s" % ("ALL PASS" if not fails else "FAILED %d" % fails))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--meas", default=str(MEAS))
    ap.add_argument("--out", default="reports/kinetics_calibration_20261106.json")
    args = ap.parse_args()
    if args.selftest:
        return selftest()

    p = Path(args.meas)
    if not p.exists():
        print("找不到测量文件：%s\n先用 --selftest 验证拟合器，或按文件头格式建数据。" % p)
        return 2
    datasets = load_measurements(p)
    res = analyse(datasets)
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print("数据集 %d 组，可用 %d 组"
          % (len(res["datasets"]),
             sum(1 for d in res["datasets"] if d.get("k_per_min"))))
    for rxn, info in res["by_reaction"].items():
        q = info["q10_mean"]
        d = info["q10_delta"]
        print("  %-24s T=%-14s Q10=%-6s (当前 %s，差 %s)  Ea=%s"
              % (rxn, info["temperatures_C"],
                 ("%.2f" % q) if q else "—",
                 ("%.2f" % info["q10_current"]) if info["q10_current"] else "—",
                 ("%+.2f" % d) if d is not None else "—",
                 ("%.1f kJ/mol" % info["arrhenius"]["ea_kJ_per_mol"])
                 if info["arrhenius"] else "—"))
    print("当前 kinetics.json q10 = %s"
          % ((res["current_params"].get("q10") or {}).get("value")))
    print("写出 %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
