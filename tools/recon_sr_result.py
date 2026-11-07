# -*- coding: utf-8 -*-
r"""确认 SmartReact 枚举结果的字段（我门控要用 reaction_name）。"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
from smartreact import ReactionEnumerator

e = ReactionEnumerator()
res = e.enumerate_pair("CC(=O)O", "CCN")
print(f"enumerate_pair 返回 {len(res)} 条")
if res:
    r = res[0]
    print("类型:", type(r).__name__)
    print("字段:", [a for a in dir(r) if not a.startswith("_")])
    for f in ("reaction_name", "reactant_a", "reactant_b", "products", "template", "tid"):
        print(f"   {f} = {str(getattr(r, f, '<无>'))[:80]}")
print()
print("条件表文件是否存在:")
for f in ("conditions_normalized.json", "conditions_by_reaction_type.json"):
    p = STAGE / "reports" / f
    print(f"   {f}: {p.exists()}")
