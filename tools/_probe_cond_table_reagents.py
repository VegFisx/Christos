# -*- coding: utf-8 -*-
r"""一次性：条件表里到底存了什么（B-H 的 reagents/catalysts 字段是不是带 SMILES）。"""
from __future__ import annotations

import json
import sys
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

from smartreact_engine import SmartReactEngine  # noqa: E402

eng = SmartReactEngine()
e = eng.cond_table.get("B-H") or {}
print("B-H 条目：")
print(json.dumps({k: v for k, v in e.items()
                  if k in ("reagents", "catalysts", "bases", "n_ord_matched",
                           "auxiliary_reagents", "ph", "time_min")},
                 ensure_ascii=False, indent=1)[:2200])

# 再看两个别的类的 reagents 字段形态，确认是不是同一个 schema
for rn in ("mitsunobu", "amide_coupling"):
    ee = eng.cond_table.get(rn) or {}
    print(f"\n{rn}: reagents 前 3 = {list((ee.get('reagents') or [])[:3])}")
    print(f"        catalysts 前 3 = {list((ee.get('catalysts') or [])[:3])}")
