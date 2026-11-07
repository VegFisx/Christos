# -*- coding: utf-8 -*-
"""检查：第 6 轮那次 derive --apply 有没有覆盖掉原本正确的配平值。

对比 rules.backup-before-draft.json（加草稿之前）与当前文件，
把 co_reagents / byproducts 发生变化的原始规则列出来。
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules")
OLD = STAGE / "rules.backup-before-draft.json"
NEW = STAGE / "rules.json"

old = {r["id"]: r for r in json.loads(OLD.read_text(encoding="utf-8"))["rules"]}
new = {r["id"]: r for r in json.loads(NEW.read_text(encoding="utf-8"))["rules"]}

print("=" * 90)
print("原始 24 条规则里，配平值被改动的：")
print("=" * 90)
changed = []
for rid, o in old.items():
    n = new.get(rid)
    if n is None:
        print(f"  [已删除] {o['name']}")
        continue
    oc = (o.get("co_reagents") or {}, o.get("byproducts") or {})
    nc = (n.get("co_reagents") or {}, n.get("byproducts") or {})
    if oc != nc:
        changed.append(rid)
        print(f"\n  【{o['name']}】{rid}")
        print(f"     改前: co={oc[0]}  by={oc[1]}")
        print(f"     改后: co={nc[0]}  by={nc[1]}")

if not changed:
    print("  （无）")

# 判断哪些改动是「变坏」的：产物类型与反应类别不符
print()
print("=" * 90)
print("其中疑似「越改越错」的（副产物与反应类别不符）：")
print("=" * 90)
PLAUSIBLE = {
    "hydrolysis": {"H2O"}, "condensation": {"H2O"}, "esterification": {"H2O"},
    "oxidation": {"H2O", "H2O2"}, "reduction": {"H2O"},
    "hydroxylation": {"H2O"}, "cyclization": {"H2O", "H2"},
    "elimination": {"H2O", "NH3", "H2"}, "decarboxylation": {"CO2", "H2O"},
}
bad = []
for rid in changed:
    n = new[rid]
    by = (n.get("byproducts") or {})
    cat = n.get("category", "")
    allowed = PLAUSIBLE.get(cat)
    if allowed is None:
        continue
    for f in by:
        if f not in allowed:
            bad.append((rid, n["name"], cat, f, sorted(allowed)))
            print(f"  ★【{n['name']}】{cat} 类却写了副产物 {f}"
                  f"（该类合理的副产物：{sorted(allowed)}）")

if not bad:
    print("  （无）")
print(f"\n共 {len(changed)} 条被改，其中 {len(bad)} 条疑似改错")
