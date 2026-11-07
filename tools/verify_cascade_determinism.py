# -*- coding: utf-8 -*-
"""验证级联的可复现性：同一批成分、同一顺序，跑两次应完全一致。"""
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

import compat
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


comps = []
for h in ("甘草", "附子"):
    for r in find_compounds(h, limit=15):
        r = dict(r)
        r["herb_name"] = h
        r["source"] = h
        comps.append(r)
print(f"成分 {len(comps)} 个")


def run(cs):
    r = compat.find_final_products(cs, max_rounds=8, frontier_limit=60,
                                   min_new=10, conditions="煎煮", threshold=0.0)
    return {canon(p["smiles"]) for p in r["products"]}, r


a, ra = run(comps)
b, rb = run(comps)
print(f"  第一次 {len(a)} 个产物，{ra['rounds']} 轮")
print(f"  第二次 {len(b)} 个产物，{rb['rounds']} 轮")
print(f"  ★ 完全相同: {a == b}   交集 {len(a & b)}  对称差 {len(a ^ b)}")

# 三次不同顺序的稳定性
import random
sets = []
for seed in (11, 22, 33):
    cs = list(comps)
    random.Random(seed).shuffle(cs)
    s, _ = run(cs)
    sets.append(s)
print()
print("  打乱顺序三次的两两覆盖率：")
for i in range(3):
    for j in range(i + 1, 3):
        cov = 100 * len(sets[i] & sets[j]) / max(1, min(len(sets[i]), len(sets[j])))
        print(f"    {i+1} vs {j+1}: {cov:.1f}%")
