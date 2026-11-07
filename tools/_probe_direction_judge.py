# -*- coding: utf-8 -*-
"""一次性：校验方向判据表与 LABELS 枚举一致，并抽查几个关键判定。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import direction as D          # noqa: E402
import templates as T          # noqa: E402

t = D.load_table()
bad = [fam for fam, d in (t.get("families") or {}).items()
       if d.get("label") not in D.LABELS]
print("表里不在 LABELS 枚举内的家族 =", bad or "无")

cond = T.get_template("煎煮")
print(f"条件 = {cond.describe()}")
for rn in ("esterification", "suzuki", "mined_mono", "C_C_decarboxylation",
           "williamson", "reductive_amination_ketone", "amide_coupling"):
    j = D.judge(rn, cond)
    print(f"  {rn:<28} -> {j['label']:<10} {j['label_cn']:<6} src={j['source']:<26} "
          f"{j['reason'][:40]}")
print()
cond2 = T.get_template("醇提")
j = D.judge("esterification", cond2)
print(f"醇提下 esterification -> {j['label_cn']}（期望 方向明确） 介质桶={j['medium']}")
