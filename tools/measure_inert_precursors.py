# -*- coding: utf-8 -*-
r"""量化：逆合成路线里的"惰性小分子前体"占比（CC/CCl/CO/H2O 这类）。"""
import sys
from collections import Counter
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (STAGE/"tools", STAGE/"libs", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from retro_search import RetroSearch, load_available, load_retro_templates, load_purchasable_blocks

TARGETS = [
    "COc1cc2c(cc1O)oc1cc(O)cc(O)c1c2=O",          # 5-methoxymarmesin
    "CC(C)=CCc1c(O)cc(O)c2c(=O)cc(-c3cc(O)c(O)c(CC=C(C)C)c3)oc12",  # 异戊烯基黄酮
    "Cn1cnc2c1c(=O)n(C)c(=O)n2C",                 # 咖啡因
    "OC[C@@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",  # 葡萄糖
    "O=C(NCCc1ccc(O)cc1)c1ccccc1O",               # 水杨酰胺
]
tmpl = load_retro_templates(); av = load_available(); bf, bs = load_purchasable_blocks()
eng = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs, filter_weird=True, weird_charged=True, skel_tol=1)

hac_hist = Counter()
per_type_small = Counter()
per_type_all = Counter()
n_routes = 0
examples = []
for smi in TARGETS:
    for st in eng.disconnections(smi):
        hits = [(p, eng.is_available(p)) for p in st.precursors]
        if not all(h[1] for h in hits):
            continue
        n_routes += 1
        per_type_all[st.reaction_name] += 1
        has_small = False
        for p, _ in hits:
            m = Chem.MolFromSmiles(p)
            h = m.GetNumHeavyAtoms() if m else -1
            hac_hist[h] += 1
            if h <= 2:
                has_small = True
        if has_small:
            per_type_small[st.reaction_name] += 1
            if len(examples) < 10:
                examples.append((st.reaction_name, [p for p, _ in hits]))

print(f"5 个目标上'全部前体可得'的路线 {n_routes} 条")
print("\n前体重原子数分布（重原子数: 出现次数）：")
for h in sorted(hac_hist):
    print(f"   {h:>3} 原子 : {hac_hist[h]:>6,}  ({hac_hist[h]/sum(hac_hist.values())*100:5.1f}%)")
small = sum(v for k, v in hac_hist.items() if k <= 2)
print(f"\n★ 惰性小分子(<=2 重原子: 水/甲醇/乙烷/氯甲烷/CO2…)占全部前体的 "
      f"{small}/{sum(hac_hist.values())} = {small/sum(hac_hist.values())*100:.1f}%")
print("\n含这类小分子的路线占比，按反应类型（前 12）：")
rows = sorted(((per_type_small[k]/per_type_all[k], per_type_small[k], per_type_all[k], k)
               for k in per_type_all if per_type_all[k] >= 20), reverse=True)
for r, b, a, k in rows[:12]:
    print(f"   {r*100:5.1f}%  {b:>5}/{a:<5} {k}")
print("\n例子:")
for tn, pres in examples:
    print(f"   [{tn}] {pres}")
