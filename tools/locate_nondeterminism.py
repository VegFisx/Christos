# -*- coding: utf-8 -*-
r"""定位两处确定性问题。

① cascade 残余 5 个差异 —— 猜：产物归属的 source_smiles 取决于"哪个底物先处理"
② 多样性排序 —— 同分时按列表顺序破平
"""
import random
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
TCMAI_SRC = Path(r"D:\TCMAI\src")
sys.path.insert(0, str(TCMAI_SRC))
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
from cascade import cascade
import templates as T
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


raw = []
for h in ("甘草", "附子"):
    for r in find_compounds(h, limit=10):
        raw.append(dict(r))
print(f"底物 {len(raw)} 个\n")

print("=" * 96)
print("① 假设：产物归属的 source_smiles 取决于底物处理顺序")
print("=" * 96)


def step_map(seq):
    subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
            for c in seq if get_mol(c["smiles"])]
    ps = eng.step(subs, cond, 0.15, round_no=1)
    return {canon(p.smiles): (p.rule_id, p.source_smiles) for p in ps if canon(p.smiles)}


def shuf(seq, seed):
    o = list(seq)
    random.Random(seed).shuffle(o)
    return o


m1 = step_map(raw)
m2 = step_map(shuf(raw, 7))
print(f"  产物集合: {len(m1)} vs {len(m2)}  集合相同={set(m1) == set(m2)}")
diff_src = [k for k in set(m1) & set(m2) if m1[k] != m2[k]]
print(f"  ★ 归属不同的产物: {len(diff_src)}")
for k in diff_src[:4]:
    print(f"      {k[:52]}")
    print(f"        序1: rule={m1[k][0]} 源={m1[k][1][:44]}")
    print(f"        序2: rule={m2[k][0]} 源={m2[k][1][:44]}")

print()
print("=" * 96)
print("② 多样性排序：同分有多严重？")
print("=" * 96)
subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in raw if get_mol(c["smiles"])]
r = cascade(eng, subs, cond, max_rounds=5, min_new=10, frontier_limit=40)
prods = [p for p in r.products if not p.is_byproduct]
sc = Counter(round(p.score, 6) for p in prods)
print(f"  产物池 {len(prods)}")
print(f"  不同分数值 {len(sc)} 个；最多的几个分数：")
for v, n in sc.most_common(5):
    print(f"      {v}  重复 {n} 次")
dup = sum(n for v, n in sc.items() if n > 1)
print(f"  ★ 有并列的产物共 {dup} 个（{100*dup/len(prods):.0f}%）")


def diverse_top(pool, top=20):
    remaining = list(pool)
    selected = []
    used = Counter()
    while remaining and len(selected) < top:
        best, best_adj = None, None
        for p in remaining:
            adj = p.score - 0.12 * used[p.rule_id]
            if best_adj is None or adj > best_adj:
                best, best_adj = p, adj
        selected.append(best)
        used[best.rule_id] += 1
        remaining.remove(best)
    return selected


t1 = diverse_top(prods)
o = list(prods)
random.Random(3).shuffle(o)
t2 = diverse_top(o)
print(f"  两种顺序的 Top-20 完全相同: {[p.smiles for p in t1] == [p.smiles for p in t2]}")
print(f"  共有: {len({p.smiles for p in t1} & {p.smiles for p in t2})}/20")

print()
print("=" * 96)
print("判定")
print("=" * 96)
print("""
  ① 若归属确实随顺序变 → 修法：在 step 里先把底物按 SMILES 排序，
     让"哪个底物先产出"变得确定。
  ② 若同分比例很高 → 多样性排序必须加确定性的破平键（按 SMILES）。
""")
