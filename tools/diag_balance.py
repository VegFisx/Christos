# -*- coding: utf-8 -*-
"""诊断：失衡到底是真的，还是我的校验方法污染了输入分子？

假设：rdkit 的 RunReactants 会在同一个 Mol 对象上反复操作，
      复用同一个 mol 去跑多条规则 / 多次运行，可能导致产物原子数异常。
测试：分别用「共享 mol」和「每次重新解析的 mol」跑同一个失败案例。
"""
import sqlite3
import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\rules")

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import atom_counts, formula_atoms, add_atoms, atom_diff, format_atoms

DB = r"D:\TCMAI\tcm.db"


def fetch(name_like):
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT name_en, smiles FROM compounds WHERE name_en LIKE ? LIMIT 1",
                (f"%{name_like}%",))
    row = cur.fetchone()
    conn.close()
    return row


def run_case(label, smarts, smiles, co=None, by=None):
    co_atoms = formula_atoms(co, "co") if co else {}
    by_atoms = formula_atoms(by, "by") if by else {}
    rxn = AllChem.ReactionFromSmarts(smarts)

    print(f"\n{'='*76}")
    print(f"{label}")
    print(f"  底物 SMILES: {smiles[:100]}")
    m0 = Chem.MolFromSmiles(smiles)
    print(f"  底物分子式: {rdMolDescriptors.CalcMolFormula(m0)}  "
          f"原子: {format_atoms(atom_counts(m0))}")

    # --- 方式 A：复用同一个 mol 对象（我原来校验器的做法）---
    shared = Chem.Mol(m0)
    res_a = rxn.RunReactants((shared,))
    a_diff = None
    if res_a:
        left = add_atoms(atom_counts(m0), co_atoms)
        right = dict(by_atoms)
        for p in res_a[0]:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
            except Exception:
                pass
            right = add_atoms(right, atom_counts(pc))
        a_diff = atom_diff(left, right)

    # --- 方式 B：每次都用全新的 mol ---
    fresh = Chem.MolFromSmiles(smiles)
    res_b = rxn.RunReactants((fresh,))
    b_diff = None
    if res_b:
        left = add_atoms(atom_counts(Chem.MolFromSmiles(smiles)), co_atoms)
        right = dict(by_atoms)
        for p in res_b[0]:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
            except Exception:
                pass
            right = add_atoms(right, atom_counts(pc))
        b_diff = atom_diff(left, right)

    print(f"  产物集合数: {len(res_b) if res_b else 0}")
    print(f"  [A 共享mol ] 右减左: {a_diff if a_diff else '配平'}")
    print(f"  [B 全新mol ] 右减左: {b_diff if b_diff else '配平'}")

    # --- 列出前两个产物集合的组成 ---
    if res_b:
        for i, pset in enumerate(res_b[:2]):
            frags = []
            for p in pset:
                pc = Chem.Mol(p)
                try:
                    Chem.SanitizeMol(pc)
                    frags.append(f"{rdMolDescriptors.CalcMolFormula(pc)}")
                except Exception:
                    frags.append("(价态非法)")
            print(f"    产物集合{i+1}: " + " + ".join(frags))

    # --- 检验：同样的 mol 被反复用，原子数会不会变 ---
    probe = Chem.MolFromSmiles(smiles)
    before = atom_counts(probe)
    for _ in range(3):
        rxn.RunReactants((probe,))
    after = atom_counts(probe)
    print(f"  反复跑 3 次后，底物原子数变化: {atom_diff(before, after) or '无变化'}")


print("#" * 76)
print("# 案例 1：酯水解（实测 120/764 失衡）")
print("#" * 76)
row = fetch("Adinoside d")
if row:
    run_case("酯水解 / Adinoside d",
             "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]",
             row[1], co={"H2O": 1})

print()
print("#" * 76)
print("# 案例 2：糖苷水解（实测 64/798 失衡）")
print("#" * 76)
row = fetch("10-dehydrohecogenin")
if row:
    run_case("糖苷水解 / 10-dehydrohecogenin",
             "[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][C:8]"
             ">>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][C:8]",
             row[1], co={"H2O": 1})

print()
print("#" * 76)
print("# 案例 3：缩醛水解（我改过的 SMARTS，26/1212 配平）")
print("#" * 76)
row = fetch("Oleanolic acid-3-o-beta-d-xylopyranoside")
if row:
    run_case("缩醛水解(改) / Oleanolic acid 3-O-木糖苷",
             "[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]"
             ">>[CX3H1:1]=[OX1:2].[OH:4][#6:5].[OH][#6:3]",
             row[1], co={"H2O": 1})

print()
print("#" * 76)
print("# 案例 4：酮-烯醇化（6/513 失衡，其中一例差 -65 C）")
print("#" * 76)
row = fetch("methyl-5'-hydroxy jasmonat")
if row:
    run_case("酮-烯醇化 / methyl jasmonate 衍生物",
             "[CX3:1](=[OX1:2])[CX4H2:3]>>[C:1]([OH:2])=[C:3]",
             row[1])
