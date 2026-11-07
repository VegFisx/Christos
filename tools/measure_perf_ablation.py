# -*- coding: utf-8 -*-
r"""干净的四组对照：分别测出【缓存】和【预筛】各自的贡献。

上一版对照的缺陷：只关掉了预筛，缓存还在生效 → 测出来只有 1.06×。
这次四种组合都测：

  A  原始（无缓存 + 无预筛）
  B  只加缓存
  C  只加预筛（缓存关掉）
  D  都有（当前实现）
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
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")

comps = []
for h in ("甘草", "附子", "干姜"):
    for r in find_compounds(h, limit=20):
        comps.append(dict(r))
subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in comps if get_mol(c["smiles"])]
print(f"底物 {len(subs)} 个\n")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


# 保留原始方法
ORIG_REACTANTS = eng._reactants_obj
ORIG_PREFILTER = eng._achiral_matches


def no_cache(self, smiles):
    """不做缓存：每次重新构造 rdchiralReactants。"""
    from rdchiral.main import rdchiralReactants
    return rdchiralReactants(smiles)


def no_prefilter(self, rule, r_obj):
    return True


def run(cache_on, prefilter_on, label):
    if cache_on:
        eng._reactants_obj = ORIG_REACTANTS.__get__(eng, type(eng))
    else:
        eng._reactants_obj = no_cache.__get__(eng, type(eng))
    if prefilter_on:
        eng._achiral_matches = ORIG_PREFILTER.__get__(eng, type(eng))
    else:
        eng._achiral_matches = no_prefilter.__get__(eng, type(eng))

    eng._reactants_cache = {}
    eng.prefilter_skipped = 0
    t0 = time.time()
    ps = eng.step(subs, cond, 0.15, round_no=1)
    dt = time.time() - t0
    s = {canon(p.smiles) for p in ps}
    s.discard(None)
    print(f"  {label:<28}{dt:>7.2f}s{len(s):>7} 个{eng.prefilter_skipped:>8} 次跳过")
    return dt, s


print("=" * 96)
print("四组对照（底物 59 个，煎煮条件）")
print("=" * 96)
print(f"  {'配置':<28}{'耗时':>8}{'产物':>8}{'预筛跳过':>12}")
print("  " + "-" * 58)

tA, sA = run(False, False, "A 原始（无缓存无预筛）")
tB, sB = run(True, False, "B 只加缓存")
tC, sC = run(False, True, "C 只加预筛")
tD, sD = run(True, True, "D 都有（当前）")

# 恢复
eng._reactants_obj = ORIG_REACTANTS.__get__(eng, type(eng))
eng._achiral_matches = ORIG_PREFILTER.__get__(eng, type(eng))

print()
print("=" * 96)
print("结论")
print("=" * 96)
print(f"  原始 → 当前       : {tA:.2f}s → {tD:.2f}s   加速 {tA/max(tD,1e-9):.2f}×")
print(f"  缓存的贡献         : {tA:.2f}s → {tB:.2f}s   加速 {tA/max(tB,1e-9):.2f}×")
print(f"  预筛的贡献         : {tA:.2f}s → {tC:.2f}s   加速 {tA/max(tC,1e-9):.2f}×")
print()
print(f"  ★ 产物集合是否一致 ★")
for label, s in (("A", sA), ("B", sB), ("C", sC), ("D", sD)):
    print(f"      {label}: {len(s)} 个，与 D 的对称差 {len(s ^ sD)}")
allok = all(s == sD for s in (sA, sB, sC))
print(f"  → {'✓ 四组产物完全相同' if allok else '✗ 有差异！'}")
