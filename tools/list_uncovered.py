# -*- coding: utf-8 -*-
"""列出测试集尚未覆盖的启用规则，为扩充用例做指引。"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "conditions", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from schema import load_rules

profiles, rules = load_rules(str(STAGE / "rules" / "rules.json"))
cases = json.loads((STAGE / "tools" / "reaction_cases.json").read_text(encoding="utf-8"))
covered = {c["rule"] for c in cases if c.get("rule")}

active = [r for r in rules if r.get("status") != "disabled"]
active_ids = {r["id"] for r in active}
missing = [r for r in active if r["id"] not in covered]

print(f"启用中规则 {len(active)} 条")
print(f"测试集覆盖 {len(covered & active_ids)} 条")
print(f"未覆盖 {len(missing)} 条")
print()
for r in missing:
    print(f"  {r['name']:<24} {r['id']:<44} {r.get('category')}")
