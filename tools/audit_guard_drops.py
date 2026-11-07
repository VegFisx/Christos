# -*- coding: utf-8 -*-
r"""看运行时守卫到底拦了哪些规则的产物——可能还有别的隐患。

守卫在 _collect 里累加到 self.balance_dropped（一个总数）。
这里改成逐规则统计，看是哪几条规则在产出配不平的产物。
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from engine import Compound, load_engine
from schema import _load_substrates
import templates as T

eng, rules, profs = load_engine()
subs = _load_substrates(r"D:\TCMAI\tcm.db", 800)
print(f"底物 {len(subs)} 个")

# 逐规则跑，记录守卫拦下的增量
by_rule = defaultdict(int)
by_rule_first = {}
subs_small = subs[:150]

for r in rules:
    if r.get("status") == "disabled":
        continue
    for cond_name in ("煎煮", "还原", "氧化", "酸水解", "室温浸泡"):
        cond = T.get_template(cond_name)
        before = getattr(eng, "balance_dropped", 0)
        for name, smi, mol in subs_small:
            eng.apply_rule(r, Compound(smiles=smi, name=name or "", herb="t"),
                           0.6, 1, cond)
            after = getattr(eng, "balance_dropped", 0)
            if after > before:
                by_rule[r["name"]] += after - before
                if r["name"] not in by_rule_first:
                    by_rule_first[r["name"]] = (name, smi, cond_name)
                before = after

total = sum(by_rule.values())
print(f"\n守卫共拦下 {total} 组\n")
if by_rule:
    print(f"{'规则':<24}{'拦下组数':>8}   首个例子")
    print("-" * 88)
    for name, n in sorted(by_rule.items(), key=lambda x: -x[1]):
        ex = by_rule_first[name]
        print(f"{name:<24}{n:>8}   {ex[0][:34]} / {ex[2]}")
        print(f"{'':<24}{'':>8}   {ex[1][:70]}")
else:
    print("（无）")

print()
print("=" * 88)
print("判定")
print("=" * 88)
print("""
  若集中在少数几条规则 → 那些规则要单独看
  若分散在很多规则   → 可能是守卫太严（误杀），要重新评估
""")
