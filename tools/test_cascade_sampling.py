# -*- coding: utf-8 -*-
r"""
检验假设：级联的差异来自【采样】，不是【引擎能力】
====================================================

单轮对比时，新引擎产物是旧引擎的【超集】（旧独有归零）。
但级联对比时覆盖率只有 8.1%。

两个可能：
  H1（采样假说）：级联有前沿上限(frontier_limit)，两个引擎的采样不同，
                  探索的是不同子空间。→ 放大前沿，覆盖率应上升。
  H2（能力假说）：新引擎【根本到不了】那些分子。→ 放大前沿也没用。

实验：把【两个引擎】的前沿上限都从 60 放大到 400，再看覆盖率。
      如果覆盖率大幅上升 → H1 成立，是采样差异，不是缺陷。
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

print("=" * 100)
print("放大前沿上限，看覆盖率怎么变")
print("=" * 100)
print(f"  {'前沿':>6}{'旧产物':>8}{'旧收敛':>8}{'新产物':>8}{'新收敛':>8}"
      f"{'共有':>8}{'旧独有':>8}{'覆盖率':>9}")
print("  " + "-" * 74)

rows = []
for FL in (60, 150, 400):
    t0 = time.time()
    try:
        old = old_cascade(comps, max_rounds=8, frontier_limit=FL, min_new=10)
        os_ = {canon(p["smiles"]) for p in old["products"]}
        os_.discard(None)
    except Exception as e:
        print(f"  旧级联 FL={FL} 失败: {e}")
        continue
    new = compat.find_final_products(comps, max_rounds=8, frontier_limit=FL,
                                     min_new=10, conditions="煎煮", threshold=0.0)
    ns_ = {canon(p["smiles"]) for p in new["products"]}
    ns_.discard(None)
    both = os_ & ns_
    cov = 100 * len(both) / max(1, len(os_))
    rows.append((FL, len(os_), old["converged"], len(ns_), new["converged"],
                 len(both), len(os_ - ns_), cov))
    print(f"  {FL:>6}{len(os_):>8}{str(old['converged']):>8}{len(ns_):>8}"
          f"{str(new['converged']):>8}{len(both):>8}{len(os_-ns_):>8}{cov:>8.1f}%"
          f"   ({time.time()-t0:.0f}s)")

print()
print("=" * 100)
print("判定")
print("=" * 100)
if len(rows) >= 2:
    first, last = rows[0], rows[-1]
    print(f"  前沿 {first[0]} → {last[0]}：覆盖率 {first[7]:.1f}% → {last[7]:.1f}%")
    if last[7] > first[7] + 10:
        print("  → ★覆盖率随前沿显著上升 → H1 成立：差异来自【采样】，不是引擎能力★")
    else:
        print("  → 覆盖率没明显上升 → H2 成立：需要查新引擎是否到不了那些分子")

print("""
  说明：
    级联是一个【有界采样遍历】——每一轮只把前 frontier_limit 个
    「不可逆产物」当作下一轮底物。两个引擎的采样顺序不同，
    探索的就是不同的子空间。放大上限后两边都会覆盖更多，
    但这不改变一个事实：**级联的输出是一个采样结果，不是完备集合。**
""")
