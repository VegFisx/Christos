# -*- coding: utf-8 -*-
"""查 rxnmapper 到底缺什么、为什么缺。"""
import importlib
import sys
import traceback
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
LIBS = STAGE / "libs"
sys.path.insert(0, str(LIBS))

print("=== 追踪 rxnmapper 的导入链 ===")
try:
    import rxnmapper
    print("  OK")
except Exception:
    tb = traceback.format_exc()
    for line in tb.splitlines()[-12:]:
        print("   ", line)

print()
print("=== jaraco 相关：venv 和 libs 各有什么 ===")
venv_sp = Path(r"D:\TCMAI\venv\Lib\site-packages")
for root, label in ((venv_sp, "venv"), (LIBS, "libs")):
    hits = [p.name for p in root.glob("jaraco*")] if root.is_dir() else []
    print(f"  {label:<6}: {hits if hits else '（无）'}")

print()
print("=== 谁需要 jaraco ===")
for mod in ("setuptools", "pymongo", "diskcache", "filelock"):
    try:
        m = importlib.import_module(mod)
        print(f"  {mod:<12} OK  {getattr(m,'__file__','')[:70]}")
    except Exception as e:
        print(f"  {mod:<12} FAIL {type(e).__name__}: {str(e)[:50]}")

print()
print("=== 试着只导入 jaraco ===")
for sub in ("jaraco", "jaraco.text", "jaraco.context", "jaraco.functools"):
    try:
        importlib.import_module(sub)
        print(f"  {sub:<20} OK")
    except Exception as e:
        print(f"  {sub:<20} FAIL {str(e)[:50]}")
