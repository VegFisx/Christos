# -*- coding: utf-8 -*-
r"""
级联对比：旧引擎 find_final_products vs 新引擎级联
==================================================

★ 为什么这块必须单独验

  前面比的是 predict_reactions（单轮），已经证明「新引擎产物是旧引擎的超集」。
  但级联（find_final_products）完全是另一回事：

    · 收敛判据不同（旧：不可逆新增 < min_new；新：分数门槛 + 不可逆新增）
    · 前沿采样不同（旧：按反应类型均分；新：按反应类型均分 + 分数门槛）
    · 轮次处理不同（新：分数含轮数衰减）

  级联是最容易出问题的地方 —— 单轮对不代表多轮对。

要回答：
  1. 两个级联都收敛吗？各几轮？
  2. 新级联的产物是不是旧级联的超集？（就像单轮那样）
  3. 产物数量差异有多大？
"""
from __future__ import annotations

import sys
import time
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

import tcm_analyzer
import compat
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


HERBS = ["甘草", "附子"]
PER = 15

comps = []
for h in HERBS:
    for r in find_compounds(h, limit=PER):
        r = dict(r)
        r["herb_name"] = h
        r["source"] = h
        comps.append(r)
print(f"方剂：{' + '.join(HERBS)}  成分 {len(comps)} 个")
print()

# ---------------- 旧级联 ----------------
print("=" * 96)
print("旧引擎 find_final_products")
print("=" * 96)
t0 = time.time()
try:
    old_res = tcm_analyzer  # noqa
    from cascade_reactions import find_final_products as old_cascade
    old = old_cascade(comps, max_rounds=8, frontier_limit=60, min_new=10)
    old_dt = time.time() - t0
    old_set = {canon(p["smiles"]) for p in old["products"]}
    old_set.discard(None)
    print(f"  产物 {old['total']}（去重 {len(old_set)}）  "
          f"{old['rounds']} 轮  收敛={old['converged']}  {old_dt:.1f}s")
    for st in old["round_stats"]:
        print(f"    第{st['round']}轮  新增 {st['new']:>4}  不可逆 {st['irreversible_new']:>4}")
except Exception as e:
    import traceback
    print(f"  ✗ 旧级联失败: {type(e).__name__}: {e}")
    traceback.print_exc()
    old_set = set()
    old = None

# ---------------- 新级联 ----------------
print()
print("=" * 96)
print("新引擎级联（同口径：阈值 0，全规则激活）")
print("=" * 96)
t0 = time.time()
new = compat.find_final_products(comps, max_rounds=8, frontier_limit=60,
                                 min_new=10, conditions="煎煮", threshold=0.0)
new_dt = time.time() - t0
new_set = {canon(p["smiles"]) for p in new["products"]}
new_set.discard(None)
print(f"  产物 {new['total']}（去重 {len(new_set)}）  "
      f"{new['rounds']} 轮  收敛={new['converged']}  {new_dt:.1f}s")
for st in new["round_stats"]:
    print(f"    第{st['round']}轮  新增 {st['new']:>4}  可传播 {st['irreversible_new']:>4}")

if old and old_set:
    print()
    print("=" * 96)
    print("★ 集合关系（关键问题：新级联是不是旧级联的超集？）")
    print("=" * 96)
    both = old_set & new_set
    only_old = old_set - new_set
    only_new = new_set - old_set
    print(f"  旧独有 : {len(only_old):>5}")
    print(f"  共有   : {len(both):>5}")
    print(f"  新独有 : {len(only_new):>5}")
    print(f"  旧级联产物的覆盖率: {100*len(both)/max(1,len(old_set)):.1f}%")
    print()
    if only_old:
        print("  「旧独有」按规则分布（前 10）：")
        c = Counter(p["rxn"] for p in old["products"] if canon(p["smiles"]) in only_old)
        for r, n in c.most_common(10):
            print(f"      {r:<24}{n:>5}")
        print()
        print("  「旧独有」例（前 5）：")
        shown = 0
        for p in old["products"]:
            if canon(p["smiles"]) in only_old and shown < 5:
                print(f"      {p['rxn']:<20}{p.get('formula',''):<13}{p['smiles'][:48]}")
                shown += 1
    else:
        print("  ✓ 没有「旧独有」—— 新级联是旧级联的超集")

    print()
    print("=" * 96)
    print("逐规则数量对比（前 20）")
    print("=" * 96)
    co = Counter(p["rxn"] for p in old["products"])
    cn = Counter(p["rxn"] for p in new["products"])
    print(f"  {'规则':<24}{'旧':>7}{'新':>7}")
    for r, n in cn.most_common(20):
        print(f"  {r:<24}{co.get(r,0):>7}{n:>7}")
