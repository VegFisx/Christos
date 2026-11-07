# -*- coding: utf-8 -*-
"""看规则库里有没有现成的分类字段可用，用于标记「气相 ΔG 不可靠」的规则。"""
import json
from pathlib import Path
from collections import Counter

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

print("规则字段:", sorted({k for r in rules for k in r}))
print()
print("category 分布（启用规则）:")
c = Counter(r.get("category", "(无)") for r in rules if r.get("status") != "disabled")
for k, v in c.most_common():
    print(f"   {str(k):<18}{v}")

print()
print("含水规则的实际 id / category:")
for r in rules:
    if r.get("status") == "disabled":
        continue
    nm = r["name"]
    if "水解" in nm or "开环" in nm or "水合" in nm:
        print(f"   {nm:<20} id={r['id']:<36} cat={r.get('category')}")
