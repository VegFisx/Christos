# -*- coding: utf-8 -*-
"""诊断级联为什么不在少数几轮内收敛。

要回答：
  · 是永不收敛，还是只是需要更多轮？
  · 增长主要来自哪些规则？
  · 前沿（frontier）是真在扩大，还是被采样上限压住了？
  · 可逆/不可逆的划分有没有起到作用？
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from engine import Compound, get_mol, load_engine
from cascade import ROUND_DECAY
from scorer import score_product, rank
import templates as T
from herb import compounds_of_herb
from activator import active_rules

engine, rules, profiles = load_engine()
rule_by_id = {r["id"]: r for r in rules}
print(f"规则 {len(rules)} 条\n")

SEEDS = compounds_of_herb("甘草", limit=15)
COND = T.get_template("煎煮")
print(f"底物: 甘草 {len(SEEDS)} 个成分")
print(f"条件: {COND.describe()}\n")

act = active_rules(rules, profiles, COND)
print(f"激活规则 {len(act)} 条：")
for r, s, _ in act:
    print(f"    {s:.3f}  {r['name']:<18} 上限 {r.get('max_products_per_molecule')}")

print()
print("=" * 92)
print("逐轮展开（手工跑，不用 cascade，方便看清细节）")
print("=" * 92)

all_smiles = {s.smiles for s in SEEDS}
frontier = list(SEEDS)
MAX_ROUNDS = 6
MIN_NEW = 10

print(f"{'轮':>3}{'前沿底物':>9}{'新增产物':>9}{'不可逆新增':>11}{'累计':>8}  耗时")
print("-" * 60)

round_rule = []
t_all = time.time()
for rnd in range(1, MAX_ROUNDS + 1):
    if not frontier:
        break
    t0 = time.time()
    step = engine.step(frontier, COND, 0.15, exclude_smiles=all_smiles, round_no=rnd)
    dt = time.time() - t0

    new, irrev = [], []
    by_rule = Counter()
    for p in step:
        if p.smiles in all_smiles:
            continue
        all_smiles.add(p.smiles)
        new.append(p)
        by_rule[p.rule_name] += 1
        if not p.reversible and not p.is_byproduct:
            irrev.append(p)

    round_rule.append(by_rule)
    print(f"{rnd:>3}{len(frontier):>9}{len(new):>9}{len(irrev):>11}"
          f"{len(all_smiles):>8}  {dt:.1f}s")

    if len(irrev) < MIN_NEW:
        print(f"    → 收敛（不可逆新增 {len(irrev)} < {MIN_NEW}）")
        break

    # 采样下一轮前沿（与 cascade 一致）
    by_rxn = defaultdict(list)
    for p in irrev:
        by_rxn[p.rule_id].append(p)
    LIMIT = 40
    if len(irrev) > LIMIT:
        per = max(1, LIMIT // max(1, len(by_rxn)))
        sel = []
        for items in by_rxn.values():
            sel.extend(items[:per])
        sel = sel[:LIMIT]
    else:
        sel = irrev
    frontier = [Compound(smiles=p.smiles, name=f"R{rnd+1}", herb="cascade")
                for p in sel]

print(f"\n总耗时 {time.time()-t_all:.1f}s")

print()
print("=" * 92)
print("各轮增长来自哪些规则")
print("=" * 92)
all_rules_seen = set()
for c in round_rule:
    all_rules_seen |= set(c)
names = sorted(all_rules_seen)
print(f"{'规则':<20}" + "".join(f"{'第'+str(i+1)+'轮':>9}" for i in range(len(round_rule))) + f"{'合计':>8}")
print("-" * (20 + 9 * len(round_rule) + 8))
totals = Counter()
for n in names:
    row = [c.get(n, 0) for c in round_rule]
    totals[n] = sum(row)
    print(f"{n:<20}" + "".join(f"{v:>9}" for v in row) + f"{totals[n]:>8}")

print()
print("按总贡献排序的 Top 8：")
for n, c in totals.most_common(8):
    rid = next((r["id"] for r in rules if r["name"] == n), "?")
    r = rule_by_id.get(rid, {})
    print(f"   {c:>5}  {n:<20} 可逆={r.get('reversible')} 上限={r.get('max_products_per_molecule')}")

print()
print("=" * 92)
print("诊断结论")
print("=" * 92)
last = round_rule[-1] if round_rule else Counter()
print(f"跑了 {len(round_rule)} 轮，共 {len(all_smiles) - len(SEEDS)} 个新产物")
print(f"最后一轮新增 {sum(last.values())} 个，主要来自：")
for n, c in last.most_common(5):
    print(f"    {c:>4}  {n}")
