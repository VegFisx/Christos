# -*- coding: utf-8 -*-
r"""测：反复调用 eng.step，产物数会不会变？（模块级缓存是否泄漏状态）"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

import engine as E
from engine import Compound, get_mol, load_engine
import templates as T
from tcm_ro import use_readonly; use_readonly(); from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


eng, rules, profs = load_engine()
cond = T.get_template("煎煮")

comps = []
for h in ("甘草", "附子", "干姜"):
    for r in find_compounds(h, limit=20):
        comps.append(dict(r))
subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in comps if get_mol(c["smiles"])]
print(f"底物 {len(subs)} 个")
print()

print("=" * 88)
print("① 同一个 engine 实例，连跑 4 次")
print("=" * 88)
sets = []
for i in range(4):
    ps = eng.step(subs, cond, 0.15, round_no=1)
    s = {canon(p.smiles) for p in ps}
    s.discard(None)
    sets.append(s)
    print(f"  第{i+1}次: {len(s)} 个产物   守卫拦下累计 {getattr(eng,'balance_dropped',0)}"
          f"   预筛跳过累计 {getattr(eng,'prefilter_skipped',0)}")
print(f"  四次完全相同: {all(s == sets[0] for s in sets)}")
if not all(s == sets[0] for s in sets):
    for i, s in enumerate(sets):
        print(f"    第{i+1}次 vs 第1次: 对称差 {len(s ^ sets[0])}")

print()
print("=" * 88)
print("② 清掉模块级缓存再跑")
print("=" * 88)
E._MOL_CACHE.clear()
E._ATOM_COUNT_CACHE.clear()
eng2, _, _ = load_engine()
ps = eng2.step(subs, cond, 0.15, round_no=1)
s = {canon(p.smiles) for p in ps}
s.discard(None)
print(f"  清缓存后: {len(s)} 个产物")
print(f"  与第1次相同: {s == sets[0]}   对称差 {len(s ^ sets[0])}")

print()
print("=" * 88)
print("③ 只清 _MOL_CACHE")
print("=" * 88)
E._MOL_CACHE.clear()
eng3, _, _ = load_engine()
ps = eng3.step(subs, cond, 0.15, round_no=1)
s = {canon(p.smiles) for p in ps}
s.discard(None)
print(f"  只清 _MOL_CACHE: {len(s)} 个产物   与第1次相同: {s == sets[0]}")

print()
print("=" * 88)
print("④ 只清 _ATOM_COUNT_CACHE")
print("=" * 88)
E._ATOM_COUNT_CACHE.clear()
eng4, _, _ = load_engine()
ps = eng4.step(subs, cond, 0.15, round_no=1)
s = {canon(p.smiles) for p in ps}
s.discard(None)
print(f"  只清 _ATOM_COUNT_CACHE: {len(s)} 个产物   与第1次相同: {s == sets[0]}")
