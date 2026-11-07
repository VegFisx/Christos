# -*- coding: utf-8 -*-
"""找出"羟基酸 → 内酯"的正确 SMARTS。

化学：HO-(CH2)n-COOH → 环状内酯 + H2O
  n=1  α-羟基酸 → 三元环内酯（极不稳定，实际不是可分离产物，不建议建规则）
  n=2  β-羟基酸 → 四元环内酯（不稳定）
  n=3  γ-羟基酸 → 五元环内酯（稳定，自然界常见）
  n=4  δ-羟基酸 → 六元环内酯（稳定）
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "rules"))
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import (atom_counts, formula_atoms, add_atoms, atom_diff,
                    format_atoms, _check_atom_maps)

print("=" * 84)
print("原规则到底错在哪")
print("=" * 84)
ORIG = "[OX2H:1][CX4:2][CX3:3](=[OX1:4])[OX2H:5]>>[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1"
print(f"  {ORIG}")
rxn = AllChem.ReactionFromSmarts(ORIG)
print(f"  反应物模板原子数: {rxn.GetReactantTemplate(0).GetNumAtoms()}")
print(f"  产物模板原子数  : {rxn.GetProductTemplate(0).GetNumAtoms()}")
print("  → 反应物模板里只有 O1-C2-C3 三个重原子，C2 必须直接连 C3，")
print("     即只匹配 α-羟基酸；但 desc 声称做 γ/δ-羟基酸。名不符实。")
print("  → 产物把 O5 也写进环里，且链上碳被丢弃。")
for probs in [_check_atom_maps(rxn)]:
    for p in probs:
        print(f"  静态检查: {p}")

print()
print("=" * 84)
print("候选写法：γ-内酯（五元环）与 δ-内酯（六元环）")
print("=" * 84)

CANDIDATES = {
    "γ-内酯（五元环）": (
        "[OX2H:1][CX4:2][CX4:5][CX4:6][CX3:3](=[OX1:4])[OX2H:7]"
        ">>[O:1]1[CX4:2][CX4:5][CX4:6][CX3:3]1=[OX1:4].[OH2:7]"
    ),
    "γ-内酯（水不编号版）": (
        "[OX2H:1][CX4:2][CX4:5][CX4:6][CX3:3](=[OX1:4])[OX2H:7]"
        ">>[O:1]1[CX4:2][CX4:5][CX4:6][CX3:3]1=[OX1:4].[OH2]"
    ),
    "δ-内酯（六元环）": (
        "[OX2H:1][CX4:2][CX4:5][CX4:6][CX4:8][CX3:3](=[OX1:4])[OX2H:7]"
        ">>[O:1]1[CX4:2][CX4:5][CX4:6][CX4:8][CX3:3]1=[OX1:4].[OH2:7]"
    ),
}

TESTS = [
    ("4-羟基丁酸   → γ-内酯", "OCCCC(=O)O",     CANDIDATES["γ-内酯（五元环）"]),
    ("3-羟基丁酸   → 不该匹配", "OCCC(=O)O",      CANDIDATES["γ-内酯（五元环）"]),
    ("5-羟基戊酸   → δ-内酯", "OCCCCC(=O)O",    CANDIDATES["δ-内酯（六元环）"]),
    ("4-羟基丁酸   → 不该匹配δ", "OCCCC(=O)O",    CANDIDATES["δ-内酯（六元环）"]),
    ("葡糖酸(多羟基酸) → γ-内酯", "OCC(O)C(O)C(O)C(=O)O", CANDIDATES["γ-内酯（五元环）"]),
]

for label, tmpl in CANDIDATES.items():
    print(f"\n【{label}】")
    print(f"   {tmpl}")
    try:
        r = AllChem.ReactionFromSmarts(tmpl)
    except Exception as e:
        print(f"   ✗ rdkit 编译失败: {e}")
        continue
    probs = _check_atom_maps(r)
    if probs:
        for p in probs:
            print(f"   ⚠ 静态检查: {p}")
    else:
        print(f"   ✓ rdkit 编译 OK，静态检查通过")
    try:
        from rdchiral.main import rdchiralReaction
        rdchiralReaction(tmpl)
        print(f"   ✓ rdchiral 接受")
    except Exception as e:
        print(f"   ✗ rdchiral 拒绝: {str(e)[:100]}")

print()
print("=" * 84)
print("用真实底物检验每个候选（rdchiral 引擎）")
print("=" * 84)
from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants

for label, tmpl in CANDIDATES.items():
    print(f"\n【{label}】")
    try:
        rxn_r = rdchiralReaction(tmpl)
    except Exception as e:
        print(f"   模板被拒: {e}")
        continue
    for tname, smi, _ in TESTS:
        mol = Chem.MolFromSmiles(smi)
        left = atom_counts(mol)
        try:
            outs = rdchiralRun(rxn_r, rdchiralReactants(smi))
        except Exception as e:
            print(f"   {tname}: 抛异常 {type(e).__name__}: {str(e)[:60]}")
            continue
        if not outs:
            print(f"   {tname}: 不匹配")
            continue
        for out in outs[:2]:
            pm = Chem.MolFromSmiles(out)
            if pm is None:
                print(f"   {tname}: 产物无法解析 {out[:40]}")
                continue
            right = atom_counts(pm)
            d = atom_diff(left, right)
            print(f"   {tname}: {rdMolDescriptors.CalcMolFormula(pm)} "
                  f"[{out[:46]}] {'配平' if not d else '★失衡 ' + str(d) + '★'}")
