# -*- coding: utf-8 -*-
r"""① engine.step 到底有没有用 active_rules 筛？② 规则名 vs ORD 反应类型名的可映射性。"""
import json
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

en = (STAGE / "core" / "engine.py").read_text(encoding="utf-8", errors="replace")
lines = en.splitlines()
print("=" * 92)
print("① engine.step 的实现")
print("=" * 92)
for i, line in enumerate(lines):
    if re.match(r"^    def step\(", line):
        for j in range(i, min(len(lines), i + 46)):
            print(f"   {j+1:>4} {lines[j][:108]}")
        break
print()
print("active_rules 在 engine.py 里出现次数:", en.count("active_rules"))
print("activation_score 出现次数:", en.count("activation_score"))

print()
print("=" * 92)
print("② 规则名 vs ORD 反应类型名")
print("=" * 92)
d = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
rules = d["rules"]
profiles = d["profiles"]
print("profiles 内容:")
print(json.dumps(profiles, ensure_ascii=False, indent=2)[:1100])
print()
print(f"{'规则名':<22}{'category':<14}{'condition_profile':<18}")
use = {}
for r in rules:
    use[r.get("condition_profile")] = use.get(r.get("condition_profile"), 0) + 1
for r in rules[:20]:
    print(f"{r['name'][:21]:<22}{r.get('category','')[:13]:<14}{str(r.get('condition_profile'))[:17]:<18}")
print("...")
print("condition_profile 使用分布:", use)

cond = json.loads((STAGE / "reports" / "conditions_by_reaction_type.json").read_text(encoding="utf-8"))
print()
print("ORD 条件表的 37 类:", sorted(cond.keys()))
