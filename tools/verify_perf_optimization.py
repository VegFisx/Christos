# -*- coding: utf-8 -*-
r"""验证性能优化：正确性 + 加速比。

★ 正确性是第一位的
  预筛和缓存都可能【静默改变结果】。所以必须：
    1. 优化前后产物【逐一比对】，必须完全相同
    2. 跑完整回归（62 条反应级用例 + 九道防线）
"""
from __future__ import annotations

import sys
import time
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
import templates as T
from activator import active_rules
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


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

# ---------------- 优化后的产物 ----------------
t0 = time.time()
ps_new = eng.step(subs, cond, 0.15, round_no=1)
t_new = time.time() - t0
set_new = {canon(p.smiles) for p in ps_new}
set_new.discard(None)
print(f"\n优化后: {len(set_new)} 个产物，{t_new:.2f}s")
print(f"  预筛跳过: {getattr(eng, 'prefilter_skipped', 0)} 次")
print(f"  缓存底物: {len(eng._reactants_cache)} 个")

# ---------------- 关掉优化，跑一遍对照 ----------------
print()
print("=" * 96)
print("★ 正确性对照：把优化关掉，产物必须完全相同")
print("=" * 96)

orig_prefilter = eng._achiral_matches
eng._achiral_matches = lambda rule, r_obj: True      # 关掉预筛
eng._reactants_cache = {}                            # 关掉缓存效果
t0 = time.time()
ps_old = eng.step(subs, cond, 0.15, round_no=1)
t_old = time.time() - t0
set_old = {canon(p.smiles) for p in ps_old}
set_old.discard(None)
print(f"关掉优化: {len(set_old)} 个产物，{t_old:.2f}s")
print(f"  加速比: {t_old/max(t_new,1e-9):.2f}×")
print()
print(f"  产物集合相同      : {set_new == set_old}")
print(f"  对称差            : {len(set_new ^ set_old)}")
if set_new != set_old:
    print("  ★ 有差异！★  仅新有:", list(set_new - set_old)[:3])
    print("              仅旧有:", list(set_old - set_new)[:3])
    sys.exit(1)

# 名称/归属也要一致
def full_map(prods):
    return {canon(p.smiles): (p.rule_id, p.formula, canon(p.source_smiles))
            for p in prods if canon(p.smiles)}

m_new, m_old = full_map(ps_new), full_map(ps_old)
diff = [k for k in set(m_new) & set(m_old) if m_new[k] != m_old[k]]
print(f"  归属/分子式不同   : {len(diff)}")

eng._achiral_matches = orig_prefilter

# ---------------- 完整级联 ----------------
print()
print("=" * 96)
print("完整级联的加速比")
print("=" * 96)
from cascade import cascade
eng._reactants_cache = {}
t0 = time.time()
r = cascade(eng, subs, cond, max_rounds=5, min_new=10, frontier_limit=40)
t_cas = time.time() - t0
print(f"  级联 5 轮: {len(r.products)} 产物，{t_cas:.1f}s")
print(f"  预筛累计跳过: {getattr(eng, 'prefilter_skipped', 0)} 次")
print(f"  rdchiralReactants 只构造了 {len(eng._reactants_cache)} 次"
      f"（原来是 规则数 × 底物数 次）")
