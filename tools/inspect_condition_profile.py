# -*- coding: utf-8 -*-
"""看 condition_profile 的真实格式。"""
import json
from pathlib import Path
from collections import Counter

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

print("=" * 88)
print("condition_profile 的类型分布")
print("=" * 88)
print(Counter(type(r.get("condition_profile")).__name__ for r in rules))

print()
print("前 12 条的实际值：")
for r in rules[:12]:
    print(f"  {r['name']:<22} {r.get('condition_profile')!r}")

print()
print("不同的 condition_profile 取值（去重）：")
vals = Counter(str(r.get("condition_profile")) for r in rules)
for v, n in vals.most_common(20):
    print(f"  {n:>3} 条  {v[:100]}")

print()
print("--- 找一条有 profile 的规则，看完整字段 ---")
for r in rules:
    cp = r.get("condition_profile")
    if cp:
        print(json.dumps(r, ensure_ascii=False, indent=2)[:1400])
        break
