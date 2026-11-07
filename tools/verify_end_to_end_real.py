# -*- coding: utf-8 -*-
r"""
端到端验证：新引擎的完整链路在真实方剂上跑得通吗？
==================================================

前面验证的都是【单条规则】或【单轮】。
本脚本跑【完整链路】：真实方剂 → 成分 → 条件激活 → 级联 → 收敛 → 产物

要回答三件事：
  1. 级联在真实方剂上收敛吗？
  2. 不同工艺（煎煮/醇提/酸水解/无氧煎煮）真的给出不同产物吗？
  3. 耗时能不能接受？

药材：四方（附子+干姜+甘草）—— 四逆汤的核心，也是你论文里用过的组合。
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

import compat
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


HERBS = ["附子", "干姜", "甘草"]
PER = 25

print("=" * 96)
print(f"端到端验证 · 方剂：{' + '.join(HERBS)}（各 {PER} 个成分）")
print("=" * 96)

comps = []
for h in HERBS:
    rows = find_compounds(h, limit=PER)
    for r in rows:
        r = dict(r)
        r["herb_name"] = h
        r["source"] = h
        comps.append(r)
    print(f"  {h:<6} {len(rows):>3} 个成分")
print(f"  合计 {len(comps)} 个")

CONDS = ["煎煮", "醇提", "酸水解", "碱水解", "无氧煎煮", "还原"]

print()
print("=" * 96)
print("各工艺下跑完整级联")
print("=" * 96)
print(f"  {'工艺':<10}{'产物':>6}{'轮数':>6}{'收敛':>6}{'独占产物':>10}{'耗时':>9}")
print("  " + "-" * 58)

results = {}
for cname in CONDS:
    t0 = time.time()
    r = compat.find_final_products(comps, max_rounds=8, frontier_limit=60,
                                   min_new=10, conditions=cname)
    dt = time.time() - t0
    results[cname] = r
    print(f"  {cname:<10}{r['total']:>6}{r['rounds']:>6}"
          f"{('是' if r['converged'] else '否'):>6}{'':>10}{dt:>8.1f}s")

# 独占产物
sets = {k: {canon(p["smiles"]) for p in v["products"]} for k, v in results.items()}
for k in sets:
    sets[k].discard(None)

print()
print("=" * 96)
print("★ 工艺之间的产物差异（这是条件层的价值）")
print("=" * 96)
base = sets["煎煮"]
for cname in CONDS[1:]:
    s = sets[cname]
    only_c = s - base
    only_b = base - s
    print(f"  {cname:<10} 只它有的 {len(only_c):>5}   只煎煮有的 {len(only_b):>5}   "
          f"共有 {len(s & base):>5}")

print()
print("  例：醇提比煎煮多出来的产物（前 8 个）")
extra = sets["醇提"] - base
cnt = Counter()
ex = []
for p in results["醇提"]["products"]:
    if canon(p["smiles"]) in extra:
        cnt[p["rxn"]] += 1
        if len(ex) < 8:
            ex.append(p)
for p in ex:
    print(f"      {p['formula']:<13}{p['rxn']:<18}{p['smiles'][:40]}")
print(f"    （按规则：{dict(cnt.most_common(5))}）")

print()
print("  例：无氧煎煮下【消失】的产物（前 6 个）—— 氧化被关掉了")
gone = base - sets["无氧煎煮"]
gcnt = Counter()
gex = []
for p in results["煎煮"]["products"]:
    if canon(p["smiles"]) in gone:
        gcnt[p["rxn"]] += 1
        if len(gex) < 6:
            gex.append(p)
for p in gex:
    print(f"      {p['formula']:<13}{p['rxn']:<18}{p['smiles'][:40]}")
print(f"    （按规则：{dict(gcnt.most_common(5))}）")

print()
print("=" * 96)
print("逐轮统计（煎煮）")
print("=" * 96)
for st in results["煎煮"]["round_stats"]:
    print(f"    第{st['round']}轮  新增 {st['new']:>4}  可传播 {st['irreversible_new']:>4}")

print()
print("=" * 96)
print("结论")
print("=" * 96)
ok_conv = all(v["converged"] for v in results.values())
print(f"  全部工艺都收敛: {'是' if ok_conv else '否'}")
print(f"  产物集合随工艺变化: {'是' if len({frozenset(s) for s in sets.values()}) == len(sets) else '否'}")
print(f"  最慢工艺耗时: {max((v['rounds'] for v in results.values()))} 轮")
