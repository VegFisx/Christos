# -*- coding: utf-8 -*-
"""一次性探针：本轮两条任务需要的依赖是否可用（不猜，直接 import）。"""
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

for m in ("numpy", "pandas", "scipy", "sklearn", "xgboost", "lightgbm", "rdkit"):
    try:
        mod = __import__(m)
        print(f"  {m:<10} OK      {getattr(mod, '__version__', '?')}")
    except Exception as e:
        print(f"  {m:<10} MISSING ({type(e).__name__})")
