# -*- coding: utf-8 -*-
r"""查清三件事：
  ① resolve_conditions 用的是 profiles 还是 ORD 条件表？
  ② rules.json 里规则的字段（有没有 co_reagents / conditions）
  ③ activator 现在有没有被 engine 真正用来「筛」而不是「标注」
"""
import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

print("=" * 92)
print("① resolve_conditions 实现")
print("=" * 92)
sc = (STAGE / "rules" / "schema.py").read_text(encoding="utf-8", errors="replace")
lines = sc.splitlines()
for i, line in enumerate(lines):
    if re.match(r"^def resolve_conditions", line.strip()):
        for j in range(i, min(len(lines), i + 40)):
            print(f"   {j+1:>4} {lines[j][:106]}")
        break

print()
print("=" * 92)
print("② rules.json 结构")
print("=" * 92)
d = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
print("顶层 keys:", list(d.keys()))
rules = d.get("rules", [])
profiles = d.get("profiles", {})
print(f"规则数 {len(rules)}   profiles 数 {len(profiles)}")
print("profiles 的 key（前 8）:", list(profiles)[:8])
if rules:
    keys = {}
    for r in rules:
        for f in r:
            keys[f] = keys.get(f, 0) + 1
    print("规则字段出现次数:")
    for f, n in sorted(keys.items(), key=lambda x: -x[1]):
        print(f"   {f:<28} {n}")
    r0 = rules[0]
    print("\n规则示例（前 1 条，截断）:")
    print(json.dumps(r0, ensure_ascii=False, indent=2)[:900])

print()
print("=" * 92)
print("③ engine 里 activator 的用法")
print("=" * 92)
en = (STAGE / "core" / "engine.py").read_text(encoding="utf-8", errors="replace")
for i, line in enumerate(en.splitlines()):
    if "active_rules" in line or "activation_score" in line:
        lo = max(0, i - 3); hi = min(len(en.splitlines()), i + 6)
        print(f"--- 行 {i+1} ---")
        for j in range(lo, hi):
            print(f"   {j+1:>4} {en.splitlines()[j][:104]}")
