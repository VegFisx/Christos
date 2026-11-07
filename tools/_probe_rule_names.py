# -*- coding: utf-8 -*-
"""一次性：打印 37 类反应的真实类名（不手写数据）。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "libs", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from smartreact_engine import _load_reaction_names, CONDENSATION_CLASSES  # noqa: E402

meta = _load_reaction_names()
print(f"类数 = {len(meta)}")
for k in sorted(meta):
    m = meta[k]
    print(f"  {k:<30} templates={m.get('n_templates')}  cats={m.get('categories')}")
print()
print("CONDENSATION_CLASSES =")
for c in sorted(CONDENSATION_CLASSES):
    print(f"  {c}")
