# -*- coding: utf-8 -*-
r"""诊断：异构体泛滥到底是「同一分子多位点」还是「多个相似分子各出一个」？

这两种情况的修法完全不同：
  · 同一分子多位点 → 加位置选择性约束（SMARTS 层面）
  · 多个相似分子    → 是数据本身的多样性，不该当成规则的错
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from engine import Compound, get_mol, load_engine
from scorer import score_product
from cascade import ROUND_DECAY, cascade
import templates as T
from herb import compounds_of_herb
from activator import active_rules

engine, rules, profiles = load_engine()
by_id = {r["id"]: r for r in rules}

print("=" * 90)
print("① 单分子测试：一个化合物跑一条规则，到底出几个产物？")
print("=" * 90)

compounds = compounds_of_herb("甘草", limit=25)
cond = T.get_template("煎煮")
act = active_rules(rules, profiles, cond)

TESTS = ["oxidation_hydroxyl_001", "hydroxylation_aromatic_001",
         "hydration_alkene_001", "oxidation_epoxide_001",
         "oxidation_dehydrogenation_enone_001", "oxidation_primary_alcohol_001"]

print(f"{'规则':<22}{'上限':>5}{'底物数':>7}{'总产物':>8}{'平均/分子':>11}{'最多一个分子出':>16}")
print("-" * 76)
for rid in TESTS:
    r = by_id.get(rid)
    if r is None:
        continue
    limit = r.get("max_products_per_molecule")
    n_sub = n_prod = 0
    per_mol = []
    for c in compounds:
        if get_mol(c.smiles) is None:
            continue
        ps = engine.apply_rule(r, c, 0.6, 1, cond)
        if ps:
            n_sub += 1
            n_prod += len(ps)
            per_mol.append(len(ps))
    avg = (n_prod / n_sub) if n_sub else 0
    mx = max(per_mol) if per_mol else 0
    print(f"{r['name']:<22}{str(limit):>5}{n_sub:>7}{n_prod:>8}{avg:>11.2f}{mx:>16}")

print()
print("=" * 90)
print("② 分子式 C42H60O16 那 28 个异构体，到底从哪来")
print("=" * 90)

seeds = compounds_of_herb("甘草", limit=25)
res = cascade(engine, seeds, cond, max_rounds=8, min_new=10, frontier_limit=40)

TARGET = "C42H60O16"
hits = [p for p in res.products if p.formula == TARGET]
print(f"分子式 {TARGET}: 共 {len(hits)} 个产物条目")
by_src = Counter(p.source_name for p in hits)
by_rule = Counter(p.rule_name for p in hits)
by_rnd = Counter(p.round for p in hits)
print(f"  来自 {len(by_src)} 个不同成分：")
for s, n in by_src.most_common(6):
    print(f"     {n:>3}  {s[:52]}")
print(f"  由 {len(by_rule)} 种规则产生：{dict(by_rule)}")
print(f"  轮次分布：{dict(sorted(by_rnd.items()))}")

print()
print("  逐个看（前 8 个）：")
for p in hits[:8]:
    print(f"    第{p.round}轮 {p.rule_name:<10} ← {p.source_name[:26]:<28}"
          f"{p.smiles[:40]}")

print()
print("=" * 90)
print("③ 全库统计：哪些规则的「异构体/分子」比最高")
print("=" * 90)

by_rule_iso = defaultdict(lambda: {"groups": set(), "products": 0, "sources": set()})
for p in res.products:
    if p.is_byproduct:
        continue
    k = p.rule_name
    by_rule_iso[k]["groups"].add(p.formula)
    by_rule_iso[k]["products"] += 1
    by_rule_iso[k]["sources"].add(p.source_smiles)

print(f"{'规则':<20}{'产物':>7}{'分子式组':>9}{'异构体/组':>11}{'涉及母体':>9}")
print("-" * 60)
rows = []
for k, v in by_rule_iso.items():
    ng = max(1, len(v["groups"]))
    iso = v["products"] / ng
    rows.append((iso, k, v["products"], ng, len(v["sources"])))
for iso, k, np_, ng, ns in sorted(rows, reverse=True)[:12]:
    print(f"{k:<20}{np_:>7}{ng:>9}{iso:>11.2f}{ns:>9}")

print()
print("=" * 90)
print("④ 结论")
print("=" * 90)
print("""
判断标准：
  · 如果「最多一个分子出几个」≈ 上限（2），说明限流是生效的，
    异构体多是因为【母体分子本来就多】+【多轮级联】——不是规则的错。
  · 如果远超上限，说明限流没生效，是引擎的 bug。
  · 如果某个规则的「异构体/组」特别高，才需要加位置选择性约束。
""")
