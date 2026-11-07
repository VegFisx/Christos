# -*- coding: utf-8 -*-
r"""旧引擎产物表的结构摸底。

admet_products_all.csv 有 39325 行，列：
    pair, from_herb, from_compound, rxn, formula, mw, smiles, hERG, AMES, ClinTox, is_toxic_name

要回答：
  · 涉及多少个药对 / 药材 / 母体成分 / 规则？
  · 每个规则产出了多少产物？
  · 这些行是不是级联多轮的？（同一母体能被多条规则作用）
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

CSV = Path(r"D:\TCMAI\docs\reports\admet_products_all.csv")

pairs, herbs, comps, rxns = Counter(), Counter(), Counter(), Counter()
comp_rxns = defaultdict(set)
n = 0
with CSV.open(encoding="utf-8-sig", newline="") as f:
    for row in csv.DictReader(f):
        n += 1
        pairs[row["pair"]] += 1
        herbs[row["from_herb"]] += 1
        comps[row["from_compound"]] += 1
        rxns[row["rxn"]] += 1
        comp_rxns[row["from_compound"]].add(row["rxn"])

print(f"总行数 {n}")
print()
print(f"药对 {len(pairs)} 个：")
for k, v in pairs.most_common(20):
    print(f"    {k:<20}{v:>7}")
print()
print(f"药材 {len(herbs)} 味：")
for k, v in herbs.most_common(20):
    print(f"    {k:<16}{v:>7}")
print()
print(f"母体成分 {len(comps)} 个（前 15）:")
for k, v in comps.most_common(15):
    print(f"    {v:>5}  {k[:60]}")
print()
print(f"涉及的规则 {len(rxns)} 条：")
for k, v in rxns.most_common(30):
    print(f"    {k:<24}{v:>7}")

print()
print("每个母体平均被几条规则作用:")
cnt = Counter(len(v) for v in comp_rxns.values())
for k in sorted(cnt):
    print(f"    被 {k} 条规则作用: {cnt[k]} 个母体")
