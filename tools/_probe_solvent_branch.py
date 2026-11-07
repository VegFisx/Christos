# -*- coding: utf-8 -*-
"""一次性：HTE 那批条件在 B-H 上到底走哪个分支（DMSO 到底是被谁扣分的）。"""
from __future__ import annotations

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

from model import Conditions, solvent_class, solvent_matches  # noqa: E402
from smartreact_engine import SmartReactEngine               # noqa: E402

eng = SmartReactEngine()
e = eng.cond_table.get("B-H") or {}
sols = e.get("solvents") or []
print(f"B-H 偏好溶剂 = {sols}")
for name in ("DMSO", "dmso", "1,4-Dioxane", "t-AmOH", "DMA", "Toluene", "water",
             "MeCN", "2-Me-THF"):
    print(f"  {name:<12} class={solvent_class(name):<10} "
          f"matches={solvent_matches(name, sols)}")

print("\n各溶剂下的 B-H activation（催化剂/碱都给齐，只变溶剂）：")
for name, cat, base in (("DMSO", "tBuXPhos-Pd-G3", "tAmOK"),
                        ("1,4-Dioxane", "tBuXPhos-Pd-G3", "tAmOK"),
                        ("Toluene", "tBuXPhos-Pd-G3", "tAmOK"),
                        ("t-AmOH", "tBuXPhos-Pd-G3", "tAmOK"),
                        ("water", "tBuXPhos-Pd-G3", "tAmOK"),
                        ("DMA", "tBuXPhos-Pd-G3", "tAmOK")):
    cond = Conditions(solvent=name.lower(), temperature=100.0, time_min=60.0, pH=7.0,
                      catalyst="metal", atmosphere="air", reagents=(cat, base))
    s, why = eng.cond_activation("B-H", cond)
    print(f"  {name:<14} -> {s}  {why[:70]}")
