# -*- coding: utf-8 -*-
r"""一次性：cond_activation 的每个分支实际被走到多少次（弄清 0.5/0.6/1.0 是从哪来的）。

只回答一个问题：B-H 这类反应**到底有没有 ORD 条件数据**、那三个常数分别出自哪个分支。
"""
from __future__ import annotations

import sys
from collections import Counter
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

from smartreact_engine import SmartReactEngine, _load_reaction_names  # noqa: E402

eng = SmartReactEngine()
names = set(_load_reaction_names().keys())
have = set(eng.cond_table.keys())
print(f"37 类里：有 ORD 条件数据的 {len(have & names)} 类，无数据的 {len(names - have)} 类")
print(f"  无数据的类：{sorted(names - have)}")

e = eng.cond_table.get("B-H")
print(f"\nB-H 的条件表条目字段：{sorted((e or {}).keys())}")
if e:
    print(f"  temp_C      = {e.get('temp_C')}")
    print(f"  solvents    = {e.get('solvents')}")
    aux = e.get("auxiliary_reagents") or []
    print(f"  auxiliary_reagents 条数 = {len(aux)}")
    for x in aux[:10]:
        if isinstance(x, dict):
            print(f"     {str(x.get('name'))[:40]:<42} coverage={x.get('coverage')}")
        else:
            print(f"     {x}")

# 逐分支统计：用 HTE 的真实条件跑一遍，按 reason 前缀归类
import csv  # noqa: E402
CSV = (STAGE / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data"
       / "BH_HTE_Curated_Dataset_v20260219.csv")
from model import Conditions  # noqa: E402

def cat_class(name: str) -> str:
    t = str(name or "").lower()
    if not t:
        return "none"
    for k in ("pd", "binap", "xphos", "sphos", "brettphos", "ruphos", "jackiephos",
              "g3", "g4", "xantphos", "dppf", "bippy", "pt", "ni", "cu"):
        if k in t:
            return "metal"
    for k in ("cs2co3", "k2co3", "k3po4", "kotbu", "naotbu", "dbu", "mtbd", "et3n",
              "dipea", "tmg", "btmg", "nah", "lda"):
        if k in t:
            return "base"
    return "other"

score_branch = Counter()
with open(CSV, encoding="utf-8", newline="") as f:
    for i, row in enumerate(csv.DictReader(f)):
        if i >= 3000:
            break
        cond = Conditions(solvent=str(row.get("Solvent Name", "")).lower() or "unknown",
                          temperature=100.0, time_min=60.0, pH=7.0,
                          catalyst=cat_class(row.get("Catalyst Name", "")),
                          atmosphere="air",
                          reagents=(str(row.get("Catalyst Name", "")),
                                    str(row.get("Base Name", ""))))
        s, why = eng.cond_activation("B-H", cond)
        key = (round(s, 2), why.split("，")[0][:46])
        score_branch[key] += 1

print(f"\n3000 条真实条件下 (分数, 原因) 分布：")
for (s, w), n in score_branch.most_common(10):
    print(f"  {s:>4}  n={n:>5}  {w}")
