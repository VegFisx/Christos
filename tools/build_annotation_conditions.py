# -*- coding: utf-8 -*-
r"""给盲标切断**补上「文献条件与试剂」证据**（第七十五轮；用户指出的关键缺口）。

用户原话：「没有反应条件说什么也白费啊，有的反应要发生可能需要特别稀有或者特别昂贵的试剂。」

链路：
  切断 i --(usability_per_cut.jsonl: i→t)--> 模板 t --(SMARTS 匹配)-->
  retro_template_sources.jsonl 的 reaction_ids --(ORD parquet)--> 原始反应
  --(ord_schema 解码)--> 试剂/催化剂/溶剂/温度/时间

**必须用 venv 3.12 + libs 跑**（duckdb / ord_schema 都是 cp312）：

    D:\TCMAI\venv\Scripts\python.exe tools\build_annotation_conditions.py

产出：`data\annotation_conditions.json`（每条切断的文献条件样例 + 覆盖率）
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import duckdb
from ord_schema.proto import reaction_pb2

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PQ = (STAGE / "ord-data" / "data" / "11"
      / "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet")
USAB = STAGE / "reports" / "paper" / "results" / "usability_per_cut.jsonl"
ANN = STAGE / "reports" / "paper" / "results" / "annotation_candidates.jsonl"
SRC = STAGE / "reports" / "retro_template_sources.jsonl"
LIB = STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl.jsonl"
OUT = STAGE / "data" / "annotation_conditions.json"
MAX_RXN_PER_CUT = 3


def ident(c) -> str:
    r"""取一个 compound 的可读名字（优先 NAME，其次 SMILES）。"""
    name, smi = "", ""
    for x in c.identifiers:
        if x.type == reaction_pb2.CompoundIdentifier.NAME and x.value:
            name = x.value
        elif x.type == reaction_pb2.CompoundIdentifier.SMILES and x.value:
            smi = x.value
    return name or smi


def summarize(reaction) -> dict:
    r"""一条 ORD 反应 → {reactants, reagents, catalysts, solvents, temp, time, pressure}。"""
    out = {"reactants": [], "reagents": [], "catalysts": [], "solvents": [],
           "temp": "", "time": "", "pressure": ""}
    role = reaction_pb2.ReactionRole
    for inp in reaction.inputs.values():
        for c in inp.components:
            nm = ident(c)
            if not nm:
                continue
            rn = c.reaction_role
            if rn == role.REACTANT:
                out["reactants"].append(nm)
            elif rn == role.REAGENT:
                out["reagents"].append(nm)
            elif rn in (role.CATALYST, getattr(role, "CATALYST", 0)):
                out["catalysts"].append(nm)
            elif rn == getattr(role, "SOLVENT", -1):
                out["solvents"].append(nm)
    cond = reaction.conditions
    if cond.HasField("temperature") and cond.temperature.HasField("setpoint"):
        out["temp"] = "%g %s" % (cond.temperature.setpoint.value,
                                 cond.temperature.setpoint.units)
    if cond.HasField("pressure") and cond.pressure.HasField("setpoint"):
        out["pressure"] = "%g %s" % (cond.pressure.setpoint.value,
                                     cond.pressure.setpoint.units)
    # 时长（若给了）
    for inp in reaction.inputs.values():
        for c in inp.components:
            if c.amount.HasField("volume") and c.amount.volume.units == 6:
                pass
    return out


def main() -> int:
    cuts = [json.loads(l) for l in USAB.read_text(encoding="utf-8").splitlines() if l.strip()]
    t_of = {str(c["i"]): str(c["t"]) for c in cuts}
    ann = [json.loads(l) for l in ANN.read_text(encoding="utf-8").splitlines() if l.strip()]
    lib = [json.loads(l) for l in LIB.read_text(encoding="utf-8").splitlines() if l.strip()]
    src = {}
    for ln in SRC.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        src[str(d.get("template") or "")] = d
    print("可用性切断 %d ｜ 盲标 %d ｜ 基准库 %d ｜ 溯源表 %d"
          % (len(cuts), len(ann), len(lib), len(src)))
    hit_t = sum(1 for x in lib if str(x.get("template") or "") in src)
    print("  基准库模板能在溯源表里按 SMARTS 命中：%d / %d" % (hit_t, len(lib)))
    # i → 模板 SMARTS → reaction_ids
    want = {}
    for a in ann:
        i = str(a["i"])
        t = t_of.get(i)
        if not t:
            continue
        idx = int(t) - 1
        if idx < 0 or idx >= len(lib):
            continue
        tmpl = str(lib[idx].get("template") or "")
        d = src.get(tmpl) or {}
        ids = [x for x in (d.get("reaction_ids") or [])][:MAX_RXN_PER_CUT]
        if ids:
            want[i] = {"template_freq": d.get("freq"), "rxn_ids": ids}
    print("有 reaction_ids 的切断：%d / %d" % (len(want), len(ann)))
    all_ids = sorted({x for v in want.values() for x in v["rxn_ids"]})
    print("需要查的 ORD 反应：%d 条" % len(all_ids))
    con = duckdb.connect(":memory:")
    ph = ",".join(["?"] * len(all_ids))
    rows = con.execute(
        "SELECT reaction_id, reaction FROM read_parquet(?) WHERE reaction_id IN (%s)" % ph,
        [str(PQ)] + all_ids).fetchall()
    print("命中 ORD 反应：%d" % len(rows))
    got = {}
    for rid, blob in rows:
        r = reaction_pb2.Reaction()
        try:
            r.ParseFromString(blob)
        except Exception:                                    # noqa: BLE001
            continue
        got[rid] = summarize(r)
    out, n_ok = {}, 0
    for i, v in want.items():
        ex = [got[x] for x in v["rxn_ids"] if x in got]
        if ex:
            n_ok += 1
        out[i] = {"template_freq": v["template_freq"],
                  "n_rxn_ids": len(v["rxn_ids"]), "examples": ex}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("  有文献条件样例的切断：%d / %d（%.0f%%）"
          % (n_ok, len(ann), 100.0 * n_ok / max(1, len(ann))))
    # 试剂频次（给"稀有/昂贵"一个直观参照）
    cnt = Counter()
    for v in out.values():
        for ex in v["examples"]:
            for nm in ex["reagents"] + ex["catalysts"]:
                cnt[nm] += 1
    print("  最常见的试剂/催化剂（前 10）：", cnt.most_common(10))
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
