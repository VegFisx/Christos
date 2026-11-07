# -*- coding: utf-8 -*-
r"""一次性：修完溶剂后，那 7,092 个 0.5 是谁？各组成功率有差别吗？

只回答一个问题：**0.5 惩罚是不是"随机"的**（若是，AUC 必然 0.5 附近，
那说明条件层的特征本身没有区分力，而不是"方向反了"）。
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from model import Conditions                    # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

CSV = (STAGE / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data"
       / "BH_HTE_Curated_Dataset_v20260219.csv")
eng = SmartReactEngine()

stat = defaultdict(lambda: {"n": 0, "n_pos": 0, "examples": []})
scores = defaultdict(lambda: {"n": 0, "n_pos": 0})
with open(CSV, encoding="utf-8", newline="") as f:
    for i, row in enumerate(csv.DictReader(f)):
        if i >= 8000:
            break
        try:
            y = float(row.get("Yield") or 0.0)
        except ValueError:
            y = 0.0
        cond = Conditions(solvent=str(row.get("Solvent Name", "")).lower() or "unknown",
                          temperature=100.0, time_min=60.0, pH=7.0,
                          catalyst="metal", atmosphere="air",
                          reagents=(str(row.get("Catalyst Name", "")),
                                    str(row.get("Base Name", ""))))
        s, why = eng.cond_activation("B-H", cond)
        key = round(s, 2)
        scores[key]["n"] += 1
        if y >= 0.5:
            scores[key]["n_pos"] += 1
        # 只有被惩罚的记录才细看原因
        if key < 1.0:
            w = why.split("；")[0][:44] if why else "(空)"
            stat[w]["n"] += 1
            if y >= 0.5:
                stat[w]["n_pos"] += 1
            if len(stat[w]["examples"]) < 2:
                stat[w]["examples"].append(
                    f"{row.get('Catalyst Name')} + {row.get('Base Name')}")

print("按 activation 取值分组的成功率（8000 行）：")
for k in sorted(scores, reverse=True):
    d = scores[k]
    print(f"  activation {k}: n={d['n']:>5}  成功率 {d['n_pos']/max(1,d['n']):.1%}")

print("\n被惩罚（<1.0）的原因分布（前 8）：")
for w, d in sorted(stat.items(), key=lambda kv: -kv[1]["n"])[:8]:
    print(f"  n={d['n']:>5}  成功率 {d['n_pos']/max(1,d['n']):>5.1%}  {w}")
    print(f"        例: {d['examples']}")
