# -*- coding: utf-8 -*-
r"""
核心问题：激活分数高，但反应【实际能不能发生】？

例：酯化(分子间) 在酸水解下激活分数 0.450 ——
    但酸水解是【水】介质，没有醇，酯化无从发生。

可能有两种兜底机制：
  M1  co_substrate_pool 的 when_solvent 过滤（醇提才有乙醇）
  M2  什么都不兜 → 真的会在水里生成酯（那就是 bug）

本脚本直接看：这些规则在不同工艺下【实际产出多少产物】。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
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

eng, rules, profs = load_engine()
by_name = {r["name"]: r for r in rules}

print("=" * 96)
print("① 先看这些规则的 co_substrate_pool（第二反应物池）")
print("=" * 96)
for nm in ("酯化(分子间)", "酯交换", "酰胺化(分子间)", "糖苷化"):
    r = by_name.get(nm)
    if r is None:
        continue
    pool = r.get("co_substrate_pool") or []
    print(f"\n  {nm}  (co_reagents={r.get('co_reagents')})")
    if not pool:
        print("      (无 co_substrate_pool)")
    for item in pool:
        print(f"      smiles={str(item.get('smiles'))[:40]:<42} "
              f"when_solvent={item.get('when_solvent')}")

print()
print("=" * 96)
print("② 实际跑：同一批底物，在这些工艺下各产出多少")
print("=" * 96)
SUBS = [
    Compound(smiles="O=C(O)c1ccccc1", name="苯甲酸", herb="t"),
    Compound(smiles="CC(=O)O", name="乙酸", herb="t"),
    Compound(smiles="OCCO", name="乙二醇", herb="t"),
    Compound(smiles="OCC(O)CO", name="甘油", herb="t"),
]
CONDS = ["煎煮", "水提", "醇提", "酸水解", "碱水解", "酶催化"]

TARGETS = ["酯化(分子间)", "酯交换", "糖苷化", "酰胺化(分子间)",
           "酯水解", "糖苷水解", "脱水"]
print(f"  {'规则':<16}" + "".join(f"{c:>9}" for c in CONDS) + "   说明")
print("  " + "-" * 88)
verdict = []
for nm in TARGETS:
    r = by_name.get(nm)
    if r is None:
        continue
    cells = []
    for c in CONDS:
        cond = T.get_template(c)
        ps = []
        for s in SUBS:
            ps.extend(eng.apply_rule(r, s, 0.6, 1, cond))
        cells.append(len(ps))
    note = ""
    if nm in ("酯化(分子间)", "酯交换") and cells[3] == 0 and cells[2] > 0:
        note = "✓ 醇提有、酸水解无（正确）"
    elif nm in ("酯化(分子间)", "酯交换") and cells[3] > 0:
        note = "★ 酸水解下也产出了酯 ★"
        verdict.append(nm)
    print(f"  {nm:<16}" + "".join(f"{v:>9}" for v in cells) + f"   {note}")

print()
print("=" * 96)
print("③ 逐个查看：醇提 vs 酸水解 下「酯化」的实际产物")
print("=" * 96)
r = by_name.get("酯化(分子间)")
if r:
    for c in ("醇提", "酸水解", "煎煮"):
        cond = T.get_template(c)
        print(f"\n  【{c}】溶剂={cond.solvent}  温度={cond.temperature}  pH={cond.pH}")
        n = 0
        for s in SUBS:
            for p in eng.apply_rule(r, s, 0.6, 1, cond):
                print(f"      {p.formula:<12}{p.smiles[:56]}")
                n += 1
        if n == 0:
            print("      (无产物)")
        # 顺带看可用陪跑试剂
        cos = eng.available_cosubstrates(r, cond)
        print(f"      可用的第二反应物: {[c0.get('smiles') for c0 in cos]}")

print()
print("=" * 96)
print("判定")
print("=" * 96)
if verdict:
    print(f"  ★ 有问题的规则: {verdict}")
    print("     酸水解介质是水，没有醇，却在生成酯 —— 需要加 when_solvent 约束")
else:
    print("  ✓ 没有发现「水里生成酯」的问题 —— co_substrate_pool 的 when_solvent 兜住了")
