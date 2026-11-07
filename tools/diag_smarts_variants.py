# -*- coding: utf-8 -*-
"""找"禁止在环内断键"的正确 SMARTS 写法。"""
import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\rules")

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import atom_counts, formula_atoms, add_atoms, atom_diff, format_atoms

print("=" * 78)
print("候选 SMARTS 写法可用性测试")
print("=" * 78)

VARIANTS = [
    ("原写法（无约束）",        "[C:1](=[O:2])[O:3][C:4]"),
    ("!@ 非环键（键级约束）",    "[C:1](=[O:2])[O:3]!@[C:4]"),
    ("@  环键",                "[C:1](=[O:2])[O:3]@[C:4]"),
    ("[C:4;!R] 原子级约束",     "[C:1](=[O:2])[O:3][C:4;!R]"),
    ("[C:4;!r5] ",             "[C:1](=[O:2])[O:3][C:4;!r5]"),
    ("[!R] 递归写法",           "[C:1](=[O:2])[O:3][!R]"),
]
PRODUCT = ">>[C:1](=[O:2])[O:3][H].[C:4][OH]"

ok_variants = []
for label, reactant in VARIANTS:
    smarts = reactant + PRODUCT
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
        if rxn is None:
            print(f"  ✗ {label:<26} 编译返回 None")
            continue
        print(f"  ✓ {label:<26} 编译通过")
        ok_variants.append((label, smarts))
    except Exception as e:
        print(f"  ✗ {label:<26} 编译失败: {str(e)[:70]}")

print()
print("=" * 78)
print("用「链状酯」和「环内酯」分别检验每个可用写法")
print("=" * 78)

SUBSTRATES = [
    ("苯甲酸甲酯 (链状)", "COC(=O)c1ccccc1"),
    ("乙酸乙酯   (链状)", "CCOC(C)=O"),
    ("ε-己内酯   (环内)", "O=C1CCCCCO1"),
    ("γ-丁内酯   (环内)", "O=C1CCCO1"),
]
CO = {"H2O": 1}
co_atoms = formula_atoms(CO, "co")

for label, smarts in ok_variants:
    print(f"\n【{label}】")
    rxn = AllChem.ReactionFromSmarts(smarts)
    for sname, smi in SUBSTRATES:
        mol = Chem.MolFromSmiles(smi)
        left = add_atoms(atom_counts(mol), co_atoms)
        try:
            res = rxn.RunReactants((mol,))
        except Exception as e:
            print(f"    {sname}: 报错 {str(e)[:50]}")
            continue
        if not res:
            print(f"    {sname}: 不匹配（无产物）")
            continue
        verdicts = []
        for pset in res[:3]:
            right = {}
            frags = []
            for p in pset:
                pc = Chem.Mol(p)
                try:
                    Chem.SanitizeMol(pc)
                except Exception:
                    frags.append("(非法)")
                    continue
                right = add_atoms(right, atom_counts(pc))
                frags.append(rdMolDescriptors.CalcMolFormula(pc))
            d = atom_diff(left, right)
            verdicts.append(("配平" if not d else f"失衡{d}") + " [" + "+".join(frags) + "]")
        print(f"    {sname}: {' | '.join(verdicts)}")

print()
print("=" * 78)
print("结论判据")
print("=" * 78)
print("理想写法应当：链状酯 → 匹配且配平；环内酯 → 不匹配（交给专门的开环规则处理）")
