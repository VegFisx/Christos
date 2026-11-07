# -*- coding: utf-8 -*-
"""诊断：环内断键是不是"凭空造原子"的根因？

方法：同一套 SMARTS，分别喂给
  (a) 链状（非环）底物   → 期望配平
  (b) 环状底物           → 若造原子，则假设成立
"""
import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\rules")

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import atom_counts, formula_atoms, add_atoms, atom_diff, format_atoms


def test(label, smarts, smiles, co=None, by=None, expect=None):
    co_atoms = formula_atoms(co, "co") if co else {}
    by_atoms = formula_atoms(by, "by") if by else {}
    rxn = AllChem.ReactionFromSmarts(smarts)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        print(f"{label}: SMILES 解析失败")
        return
    sub_formula = rdMolDescriptors.CalcMolFormula(mol)
    # 底物里的环键数
    ring_bonds = sum(1 for b in mol.GetBonds() if b.IsInRing())

    print(f"\n{'─'*74}")
    print(f"{label}")
    print(f"  底物 : {smiles}   ({sub_formula}, 环键 {ring_bonds} 条)")
    if expect:
        print(f"  预期 : {expect}")
    try:
        res = rxn.RunReactants((mol,))
    except Exception as e:
        print(f"  RunReactants 报错: {e}")
        return
    if not res:
        print("  结果 : 无产物")
        return

    left = add_atoms(atom_counts(mol), co_atoms)
    print(f"  底物侧原子: {format_atoms(left)}   (含 co_reagents)")
    print(f"  产物集合数: {len(res)}")
    for i, pset in enumerate(res[:4]):
        right = dict(by_atoms)
        frags = []
        for p in pset:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
            except Exception:
                frags.append("(价态非法)")
                continue
            right = add_atoms(right, atom_counts(pc))
            frags.append(rdMolDescriptors.CalcMolFormula(pc))
        d = atom_diff(left, right)
        flag = "配平 ✓" if not d else f"★失衡★ 右减左 {d}"
        print(f"    集合{i+1}: {' + '.join(frags):<44} {flag}")


ESTER = "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"

print("=" * 74)
print("实验 1：酯水解 —— 链状 vs 环状")
print("=" * 74)

test("1a 苯甲酸甲酯（链状酯）", ESTER, "COC(=O)c1ccccc1",
     co={"H2O": 1}, expect="应当配平")
test("1b 乙酸乙酯（链状酯）", ESTER, "CCOC(C)=O",
     co={"H2O": 1}, expect="应当配平")
test("1c ε-己内酯（六元环内酯，环内断键）", ESTER, "O=C1CCCCCO1",
     co={"H2O": 1}, expect="如果假设成立 → 造原子")
test("1d γ-丁内酯（五元环内酯）", ESTER, "O=C1CCCO1",
     co={"H2O": 1}, expect="如果假设成立 → 造原子")
test("1e 香豆素（芳香环内酯）", ESTER, "O=c1ccc2ccccc2o1",
     co={"H2O": 1}, expect="环内断键但断的是 C-O 环键")

print()
print("=" * 74)
print("实验 2：把环键排除掉，还会不会造原子？")
print("=" * 74)
# 用 [!R] 约束：要求被断的 O-C 键不在环内
ESTER_NORING = ("[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]")
test("2a ε-己内酯 / 原 SMARTS", ESTER_NORING, "O=C1CCCCCO1", co={"H2O": 1})
# 显式要求 C:4 不在环内
ESTER_EXCL = ("[C:1](=[O:2])[O:3][C:4;!R]>>[C:1](=[O:2])[O:3][H].[C:4][OH]")
test("2b ε-己内酯 / 加 [!R] 约束 C:4 不在环内", ESTER_EXCL, "O=C1CCCCCO1",
     co={"H2O": 1}, expect="预期：不再匹配 → 无产物（这正是我们要的效果）")

print()
print("=" * 74)
print("实验 3：缩醛水解（我改过的 SMARTS）—— 链状 vs 糖环")
print("=" * 74)
ACETAL_FIXED = ("[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]"
                ">>[CX3H1:1]=[OX1:2].[OH:4][#6:5].[OH][#6:3]")
test("3a 苯甲醛二甲基缩醛（链状）", ACETAL_FIXED, "COC(OC)c1ccccc1",
     co={"H2O": 1}, expect="应当配平")
test("3b 葡萄糖（环状半缩醛）", ACETAL_FIXED, "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
     co={"H2O": 1}, expect="环内 → 可能造原子")

print()
print("=" * 74)
print("实验 4：糖苷水解 —— 链状模型 vs 真实糖苷")
print("=" * 74)
GLYCO = ("[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][C:8]"
         ">>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][C:8]")
test("4a 甲基葡萄糖苷（环状缩醛，就是糖苷）", GLYCO,
     "CO[C@H]1O[C@H](CO)[C@@H](O)[C@H](O)[C@H]1O",
     co={"H2O": 1}, expect="这是规则的目标底物，应当配平")
test("4b 水杨苷（真实中药糖苷）", GLYCO,
     "OC[C@H]1O[C@@H](Oc2ccccc2CO)[C@H](O)[C@@H](O)[C@@H]1O",
     co={"H2O": 1}, expect="应当配平")
