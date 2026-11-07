# -*- coding: utf-8 -*-
r"""
决定性实验：级联的采样有多"偶然"？
====================================

前面两个实验都没解释掉 8% 的覆盖率：
  · 放大前沿上限（60→400）：覆盖率反而降
  · 关掉分数门槛：覆盖率不变

那么真正的解释可能是：**级联的探索区域由"采样到哪些分子"决定**，
而采样对输入顺序敏感。

★ 决定性实验 ★
  同一个引擎、同一批成分，只把【输入顺序】打乱，跑三次。
  测两两覆盖率（自覆盖率）。

  若自覆盖率也 ≈ 8%  → 「新旧覆盖率 8%」毫无意义，两者都只是不同样本
  若自覆盖率很高(>90%) → 引擎是确定的，那 8% 就需要继续查
"""
from __future__ import annotations

import random
import sys
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

print("=" * 100)
print("① 同一个引擎，只打乱输入顺序，跑 3 次")
print("=" * 100)
sets = []
for seed in (1, 2, 3):
    rnd = random.Random(seed)
    shuffled = list(comps)
    rnd.shuffle(shuffled)
    r = compat.find_final_products(shuffled, max_rounds=8, frontier_limit=60,
                                   min_new=10, conditions="煎煮", threshold=0.0)
    s = {canon(p["smiles"]) for p in r["products"]}
    s.discard(None)
    sets.append(s)
    print(f"  seed={seed}  产物 {len(s):>5}  轮数 {r['rounds']}  收敛={r['converged']}")

print()
print("  两两覆盖率（自覆盖）：")
for i in range(len(sets)):
    for j in range(i + 1, len(sets)):
        a, b = sets[i], sets[j]
        cov = 100 * len(a & b) / max(1, min(len(a), len(b)))
        print(f"    seed{i+1} vs seed{j+1}:  "
              f"共有 {len(a & b):>5}  各自 {len(a):>5}/{len(b):>5}  "
              f"较小侧覆盖率 {cov:.1f}%")

print()
print("=" * 100)
print("② 顺带：按规则分布看稳定性")
print("=" * 100)
from collections import Counter
for seed, s in zip((1, 2, 3), sets):
    pass
# 重新跑一次拿产物明细
r1 = compat.find_final_products(comps, max_rounds=8, frontier_limit=60,
                                min_new=10, conditions="煎煮", threshold=0.0)
c = Counter(p["rxn"] for p in r1["products"])
print(f"  seed=0（原序）产物 {len(r1['products'])}，Top10 规则：")
for k, v in c.most_common(10):
    print(f"      {k:<24}{v:>5}")

print()
print("=" * 100)
print("判定")
print("=" * 100)
mincov = min(
    100 * len(sets[i] & sets[j]) / max(1, min(len(sets[i]), len(sets[j])))
    for i in range(len(sets)) for j in range(i + 1, len(sets))
)
print(f"  自覆盖率最小值: {mincov:.1f}%")
if mincov < 40:
    print("""
  ★ 结论：级联的输出【对输入顺序高度敏感】★

    同一个引擎、同一批成分，只打乱顺序，结果就大幅不同。
    那么「新旧引擎级联覆盖率 8%」这个数字【不能用来判断引擎好坏】——
    两者都只是庞大可达空间的【不同采样】。

    这不是缺陷，是【有界级联遍历】的固有性质：
      每轮只挑 frontier_limit 个分子继续反应，
      挑谁不挑谁，决定了后面能探索到哪。
""")
else:
    print("  引擎输出稳定，8% 需要继续查。")
