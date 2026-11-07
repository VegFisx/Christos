# -*- coding: utf-8 -*-
r"""侦察 activator.py：现有的"激活/条件"机制长什么样。"""
import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

p = STAGE / "conditions" / "activator.py"
txt = p.read_text(encoding="utf-8", errors="replace")
print("=" * 92)
print(f"activator.py（{len(txt.splitlines())} 行）")
print("=" * 92)
for line in txt.splitlines():
    s = line.strip()
    if re.match(r"^(def |class )", s):
        print("   " + s[:110])

# 看核心函数的实现（带 docstring）
lines = txt.splitlines()
for i, line in enumerate(lines):
    if re.match(r"^def (activation_score|active_rules)", line.strip()):
        print()
        print(f"--- 行 {i+1} 起 ---")
        for j in range(i, min(len(lines), i + 34)):
            print(f"   {j+1:>4} {lines[j][:106]}")

print()
print("=" * 92)
print("规则里的条件字段（rules.json）")
print("=" * 92)
rp = STAGE / "rules" / "rules.json"
if rp.exists():
    rules = json.loads(rp.read_text(encoding="utf-8"))
    if isinstance(rules, dict):
        for k in list(rules)[:3]:
            print("   顶层 key:", k)
        rules = rules.get("rules", rules)
    if isinstance(rules, list):
        print(f"   规则数 {len(rules)}")
        keys = {}
        for r in rules:
            for f in r:
                keys[f] = keys.get(f, 0) + 1
        for f, n in sorted(keys.items(), key=lambda x: -x[1]):
            print(f"      {f:<26} {n}")
        # 看一个带 co_reagents 的例子
        for r in rules:
            if r.get("co_reagents"):
                print("\n   带 co_reagents 的例子:")
                print("      name:", r.get("name"))
                print("      co_reagents:", r.get("co_reagents"))
                print("      category:", r.get("category"), " conditions:", str(r.get("conditions"))[:200])
                break
