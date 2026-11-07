# -*- coding: utf-8 -*-
r"""条件表填充率 + Engine.step 的签名（决定门控能不能接）。"""
import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
d = json.loads((STAGE / "reports" / "conditions_by_reaction_type.json").read_text(encoding="utf-8"))

print("=" * 92)
print("① 条件表填充率（37 类）")
print("=" * 92)
print(f"{'反应类型':<34}{'ORD匹配':>7}{'溶剂':>5}{'试剂':>5}{'催化':>5}{'碱':>5}{'温度':>6}")
n_filled = 0
for k, v in sorted(d.items(), key=lambda x: -x[1].get("n_ord_matched", 0)):
    ns, nr, nc, nb = (len(v.get("solvents") or []), len(v.get("reagents") or []),
                      len(v.get("catalysts") or []), len(v.get("bases") or []))
    has_t = v.get("temp_C") is not None
    if ns or nr or nc or nb or has_t:
        n_filled += 1
    print(f"{k[:33]:<34}{v.get('n_ord_matched', 0):>7}{ns:>5}{nr:>5}{nc:>5}{nb:>5}"
          f"{('有' if has_t else '-'):>6}")
print(f"\n有实质条件数据的类型: {n_filled}/37")
print(f"ORD 匹配数为 0 的类型: {sum(1 for v in d.values() if v.get('n_ord_matched',0)==0)}/37")

print()
print("=" * 92)
print("② Engine.step 与条件相关的代码")
print("=" * 92)
txt = (STAGE / "core" / "engine.py").read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
for i, line in enumerate(lines):
    if "condition" in line.lower() or "solvent" in line.lower():
        lo = max(0, i - 2); hi = min(len(lines), i + 3)
        print(f"--- 行 {i+1} 附近 ---")
        for j in range(lo, hi):
            print(f"   {j+1:>4} {lines[j][:104]}")
