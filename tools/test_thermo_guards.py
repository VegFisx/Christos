# -*- coding: utf-8 -*-
"""验证两道闸门：分子大小、ΔG 合理性。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from thermo import Thermo, MAX_HEAVY_FOR_XTB, DG_SANE_MIN, DG_SANE_MAX

th = Thermo(budget_sec=60)
print(f"Thermo 可用 : {th.available}")
print(f"大分子闸门  : > {MAX_HEAVY_FOR_XTB} 个重原子直接跳过")
print(f"ΔG 合理区间 : [{DG_SANE_MIN}, {DG_SANE_MAX}] kJ/mol")
print()

CASES = [
    ("苯甲酸 (9 重原子)", "OC(=O)c1ccccc1"),
    ("葡萄糖 (12)", "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O"),
    ("36 个碳的烷烃", "C" * 36),
    ("48 个碳的烷烃", "C" * 48),
]
print(f"{'分子':<20}{'重原子':>7}{'结果':>16}")
print("-" * 50)
from rdkit import Chem
for name, smi in CASES:
    m = Chem.MolFromSmiles(smi)
    hv = m.GetNumHeavyAtoms() if m else -1
    g = th.gibbs(smi)
    s = f"{g:.6f}" if g is not None else "被拦下"
    print(f"{name:<20}{hv:>7}{s:>16}")

print()
print(f"统计: {th.stats.summary()}")
print()
print("=== ΔG 合理性闸门 ===")
# 造一个会给出荒唐 ΔG 的组合（不守恒，只为触发数值检查）
for label, r, p in [
    ("正常：酯水解", ["CC(=O)OCC", "O"], ["CC(=O)O", "CCO"]),
    ("异常：把大烷烃算进去", ["C" * 30], ["C" * 28, "C=C"]),
]:
    dg = th.reaction_dg(r, p)
    print(f"  {label:<24} -> {dg}")
print()
print(f"统计: {th.stats.summary()}")
