# -*- coding: utf-8 -*-
r"""诊断：接入 ΔG 之后，分数到底变没变？为什么排序没变？

test_thermo_integration 有两个失败：
  · ★接入 ΔG 后排序确实改变★
  · B 组里多数产物拿到了 ΔG

要分清是「管线没生效」还是「测试预期过期」。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
from cascade import cascade
from thermo import Thermo, MAX_HEAVY_FOR_XTB
import templates as T
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
cond = T.get_template("酸水解")

comps = []
for h in ("甘草", "附子"):
    for r in find_compounds(h, limit=15):
        comps.append(dict(r))
seeds = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
         for c in comps if get_mol(c["smiles"])]
print(f"种子 {len(seeds)} 个，条件 酸水解，重原子上限 {MAX_HEAVY_FOR_XTB}")

print()
print("=" * 92)
print("A：不接 ΔG")
print("=" * 92)
resA = cascade(eng, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40, thermo=None)
realA = [p for p in resA.products if not p.is_byproduct]
print(f"  产物 {resA.total}（非副产物 {len(realA)}）")
for p in realA[:5]:
    print(f"    {p.score:.4f}  {p.formula:<12}{p.rule_name:<22}{p.smiles[:34]}")

print()
print("=" * 92)
print("B：接 ΔG")
print("=" * 92)
th = Thermo(n_conf=2)
resB = cascade(eng, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40, thermo=th)
realB = [p for p in resB.products if not p.is_byproduct]
print(f"  产物 {resB.total}（非副产物 {len(realB)}）")
print(f"  thermo_stats: {resB.thermo_stats}")
for p in realB[:5]:
    dg = f"{p.dg_kj:7.1f}" if p.dg_kj is not None else "      —"
    print(f"    {p.score:.4f}  ΔG {dg}  {p.formula:<12}{p.rule_name:<22}{p.smiles[:30]}")

print()
print("=" * 92)
print("★ 关键诊断")
print("=" * 92)
n_dg = sum(1 for p in realB if p.dg_kj is not None)
print(f"  拿到 ΔG 的产物      : {n_dg} / {len(realB)}  ({100*n_dg/max(1,len(realB)):.1f}%)")
print(f"  测试阈值 >30%       : {'通过' if n_dg > len(realB)*0.3 else '失败'}")

# 分数变了几个
mapA = {p.smiles: p.score for p in realA}
changed = [p for p in realB if p.smiles in mapA
           and abs(p.score - mapA[p.smiles]) > 1e-6]
print(f"  分数发生变化的产物  : {len(changed)} / {len(realB)}")
for p in changed[:6]:
    print(f"      {mapA[p.smiles]:.4f} → {p.score:.4f}   ΔG {p.dg_kj}   {p.rule_name}")
if not changed:
    print("      ★ 一个都没变 —— ΔG 没有进入分数 ★")

# top20
topA = [p.smiles for p in resA.products[:20]]
topB = [p.smiles for p in resB.products[:20]]
print(f"  Top20 顺序是否相同  : {'相同' if topA == topB else '不同'}")

# 重原子分布：为什么这么多被跳过
from rdkit.Chem.rdMolDescriptors import CalcNumHeavyAtoms
heavy = []
for p in realB:
    m = Chem.MolFromSmiles(p.smiles)
    if m:
        heavy.append(m.GetNumHeavyAtoms())
if heavy:
    over = sum(1 for h in heavy if h > MAX_HEAVY_FOR_XTB)
    print(f"  重原子 > {MAX_HEAVY_FOR_XTB} 被跳过的: {over} / {len(heavy)}")
    print(f"  重原子中位数: {sorted(heavy)[len(heavy)//2]}")
