# -*- coding: utf-8 -*-
r"""
决定性实验：把新级联的【分数门槛】关掉，覆盖率会不会跳上去？
==============================================================

前一个实验排除了「前沿上限」是主因（放大到 400，覆盖率反而从 8.6% 降到 6.9%）。
想清楚了：真正的原因是【分数门槛】。

  旧级联：传播【所有】不可逆产物
  新级联：只传播分数 >= MIN_PROPAGATE_SCORE(0.35) 的产物   ← 第 14 轮加的收敛机制

这是【设计差异】，不是能力差异。

若假设成立：门槛设为 0 后，新级联的覆盖率应大幅上升。
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

import compat
from cascade import cascade
from engine import Compound, load_engine, get_mol
import templates as T
from cascade_reactions import find_final_products as old_cascade
from tcm_ro import use_readonly; use_readonly(); from db_utils import find_compounds


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
print(f"成分 {len(comps)} 个\n")

# ---- 旧级联（基准） ----
old = old_cascade(comps, max_rounds=8, frontier_limit=60, min_new=10)
old_set = {canon(p["smiles"]) for p in old["products"]}
old_set.discard(None)
print(f"旧级联: {len(old_set)} 个去重产物, {old['rounds']} 轮, 收敛={old['converged']}")

# ---- 新级联：门槛扫描 ----
eng, rules, profs = load_engine()
cond = T.get_template("煎煮")
seeds = []
for c in comps:
    if get_mol(c["smiles"]):
        seeds.append(Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"]))

print()
print("=" * 100)
print("新级联：分数门槛扫描（前沿 60）")
print("=" * 100)
print(f"  {'门槛':>8}{'新产物':>9}{'轮数':>6}{'收敛':>7}{'共有':>8}{'旧独有':>8}{'覆盖率':>9}")
print("  " + "-" * 60)

for floor in (0.0, 0.15, 0.25, 0.35):
    res = cascade(eng, seeds, cond, max_rounds=8, frontier_limit=60,
                  min_new=10, min_propagate_score=floor)
    ns = {canon(p.smiles) for p in res.products}
    ns.discard(None)
    both = old_set & ns
    cov = 100 * len(both) / max(1, len(old_set))
    print(f"  {floor:>8}{len(ns):>9}{res.rounds:>6}{str(res.converged):>7}"
          f"{len(both):>8}{len(old_set - ns):>8}{cov:>8.1f}%")

print()
print("=" * 100)
print("判定")
print("=" * 100)
print("""
  若门槛=0 时覆盖率大幅上升 → ★证实：差异来自分数门槛（设计差异）★
     含义：新级联【故意】不传播低分产物（那是它收敛的原因）。
           旧级联不收敛（8 轮还在涨）正是因为它什么都传播。
  → 这不是缺陷，是「收敛」换来的选择性。
""")
