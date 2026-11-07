# -*- coding: utf-8 -*-
r"""找出【没有验收用例】的规则。

反应级验收一直报「覆盖 56/63」——那 7 条是什么？
没有用例 = 从没被任何已知答案验证过 = 最可能藏 bug 的地方。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))

rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
by_id = {r["id"]: r for r in rules}

# 用例文件
covered = set()
for f in ("reaction_cases.json", "reaction_cases2.json"):
    p = STAGE / "tools" / f
    if not p.exists():
        p = STAGE / f
    if not p.exists():
        continue
    data = json.loads(p.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("cases", [])
    for c in items:
        rid = c.get("rule_id") or c.get("rule")
        if rid:
            covered.add(rid)

print(f"用例覆盖的规则: {len(covered)} 条")
print()

print("=" * 92)
print("★ 没有验收用例的启用规则")
print("=" * 92)
uncovered = []
for r in rules:
    if r.get("status") == "disabled":
        continue
    if r["id"] not in covered:
        uncovered.append(r)

for r in uncovered:
    print(f"\n  【{r['name']}】{r['id']}")
    print(f"      类别 {r.get('category'):<16}优先级 {r.get('priority')}  "
          f"可逆 {r.get('reversible')}  上限 {r.get('max_products_per_molecule')}")
    print(f"      SMARTS: {r['smarts'][:88]}")
    print(f"      co={r.get('co_reagents')}  by={r.get('byproducts')}")

print()
print("=" * 92)
print(f"未覆盖 {len(uncovered)} / {len([r for r in rules if r.get('status')!='disabled'])} 条启用规则")
print("=" * 92)

# 已停用的呢
dis_uncovered = [r for r in rules if r.get("status") == "disabled"
                 and r["id"] not in covered]
print(f"（另有 {len(dis_uncovered)} 条已停用规则也没用例："
      f"{[r['name'] for r in dis_uncovered]}）")
