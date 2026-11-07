# -*- coding: utf-8 -*-
r"""
性能剖析：新引擎的时间到底花在哪？
====================================

已知：新引擎比旧引擎慢约 26 倍（5.3s vs 0.2s / 60 成分）。

嫌疑：
  A. rdchiral 比 rdkit 原生 RunReactants 慢
  B. 规则从 23 条增到 63 条（多 2.7 倍的机会）
  C. **绝大多数 (规则 × 底物) 组合根本不匹配，却仍然调用了 rdchiral**

先量清楚再优化。
"""
from __future__ import annotations

import cProfile
import pstats
import sys
import time
from collections import Counter
from io import StringIO
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
from rdkit.Chem import AllChem
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
import templates as T
from activator import active_rules
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")

comps = []
for h in ("甘草", "附子", "干姜"):
    for r in find_compounds(h, limit=20):
        comps.append(dict(r))
print(f"成分 {len(comps)} 个")

subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in comps if get_mol(c["smiles"])]
print(f"可解析 {len(subs)} 个")

act = active_rules(rules, profs, cond, 0.15)
print(f"煎煮激活规则 {len(act)} 条")
print()

# ---------------- ① 匹配率 ----------------
print("=" * 96)
print("① (规则 × 底物) 的匹配率 —— 有多少组合是白跑的？")
print("=" * 96)

from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants

total_pairs = 0
matched_pairs = 0
t_rdchiral = 0.0
t_all = 0.0

for rule, score, _ in act[:12]:      # 取 12 条规则做样本
    patt = eng._rdkit_reaction(rule).GetReactantTemplate(0)
    try:
        rxn_r = eng._reaction(rule)
    except Exception:
        continue
    for sub in subs[:20]:            # 每种取 20 个底物
        m = get_mol(sub.smiles)
        if m is None:
            continue
        total_pairs += 1
        # 便宜的预筛：底物是否匹配反应物模板
        if not m.HasSubstructMatch(patt):
            continue
        matched_pairs += 1
        t0 = time.time()
        try:
            rdchiralRun(rxn_r, rdchiralReactants(sub.smiles))
        except Exception:
            pass
        t_rdchiral += time.time() - t0

print(f"  样本 (规则×底物) 组合: {total_pairs}")
print(f"  其中【真正匹配】的     : {matched_pairs}  ({100*matched_pairs/max(1,total_pairs):.1f}%)")
print(f"  ★ 白跑的               : {total_pairs-matched_pairs}  "
      f"({100*(total_pairs-matched_pairs)/max(1,total_pairs):.1f}%)")
print(f"  rdchiral 累计耗时      : {t_rdchiral:.2f}s")

# ---------------- ② 便宜预筛 vs rdchiral 的单次耗时 ----------------
print()
print("=" * 96)
print("② 单次耗时对比：便宜的 SMARTS 预筛 vs rdchiral 调用")
print("=" * 96)
sample_rule = act[0][0]
patt = eng._rdkit_reaction(sample_rule).GetReactantTemplate(0)
try:
    rxn_r = eng._reaction(sample_rule)
except Exception:
    rxn_r = None

N = 200
t0 = time.time()
for sub in subs[:20]:
    m = get_mol(sub.smiles)
    if m:
        for _ in range(N // 20):
            m.HasSubstructMatch(patt)
t_cheap = time.time() - t0

if rxn_r is not None:
    t0 = time.time()
    for sub in subs[:20]:
        for _ in range(N // 20):
            try:
                rdchiralRun(rxn_r, rdchiralReactants(sub.smiles))
            except Exception:
                pass
    t_full = time.time() - t0
    print(f"  预筛 {N} 次: {t_cheap*1000:.0f} ms  ({t_cheap/N*1000:.3f} ms/次)")
    print(f"  rdchiral {N} 次: {t_full*1000:.0f} ms  ({t_full/N*1000:.3f} ms/次)")
    if t_cheap > 0:
        print(f"  ★ 预筛快 {t_full/t_cheap:.0f} 倍 ★")

# ---------------- ③ cProfile ----------------
print()
print("=" * 96)
print("③ cProfile：热函数排名")
print("=" * 96)
pr = cProfile.Profile()
pr.enable()
eng.step(subs[:25], cond, 0.15, round_no=1)
pr.disable()
s = StringIO()
ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(18)
lines = s.getvalue().splitlines()
for ln in lines[4:30]:
    print("  " + ln[:110])

# ---------------- ④ 缓存效果 ----------------
print()
print("=" * 96)
print("④ 重复调用同一底物：有没有缓存")
print("=" * 96)
t0 = time.time()
eng.step(subs[:25], cond, 0.15, round_no=1)
t_first = time.time() - t0
t0 = time.time()
eng.step(subs[:25], cond, 0.15, round_no=1)
t_second = time.time() - t0
print(f"  第一次 {t_first:.2f}s   第二次 {t_second:.2f}s   "
      f"加速 {t_first/max(t_second,1e-9):.2f}×")
