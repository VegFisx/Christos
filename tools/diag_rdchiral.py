# -*- coding: utf-8 -*-
"""关键实验：RDChiral 能不能修好"环内断键造原子"？

对比两条路线，喂同一套 SMARTS、同一批底物：
  路线 A   rdkit 原生  AllChem.ReactionFromSmarts + RunReactants
  路线 B   rdchiral    rdchiralReaction + rdchiralRun

判据仍然是：原子(底物) + 原子(co_reagents) == 原子(产物) + 原子(byproducts)
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "rules"))
sys.path.insert(0, str(STAGE / "libs"))          # rdchiral 装在这里，不动 venv

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import atom_counts, formula_atoms, add_atoms, atom_diff, format_atoms

print("=" * 80)
print("0. rdchiral 可用性")
print("=" * 80)
try:
    import rdchiral
    from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
    print(f"  ✓ rdchiral 导入成功  ({Path(rdchiral.__file__).parent})")
    RDCHIRAL_OK = True
except Exception as e:
    print(f"  ✗ rdchiral 导入失败: {type(e).__name__}: {e}")
    RDCHIRAL_OK = False

if not RDCHIRAL_OK:
    raise SystemExit(0)


def balance_rdkit(smarts, smiles, co=None, by=None, prod_limit=4):
    """路线 A"""
    co_atoms = formula_atoms(co, "co") if co else {}
    by_atoms = formula_atoms(by, "by") if by else {}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    rxn = AllChem.ReactionFromSmarts(smarts)
    try:
        res = rxn.RunReactants((mol,))
    except Exception as e:
        return [f"报错 {e}"]
    if not res:
        return []
    left = add_atoms(atom_counts(mol), co_atoms)
    out = []
    for pset in res[:prod_limit]:
        right = dict(by_atoms)
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
        out.append(("配平" if not d else f"失衡{d}") + " [" + "+".join(frags) + "]")
    return out


def balance_rdchiral(smarts, smiles, co=None, by=None):
    """路线 B"""
    co_atoms = formula_atoms(co, "co") if co else {}
    by_atoms = formula_atoms(by, "by") if by else {}
    try:
        rxn = rdchiralReaction(smarts)
        reactants = rdchiralReactants(smiles)
        outcomes = rdchiralRun(rxn, reactants)
    except Exception as e:
        return [f"报错 {type(e).__name__}: {str(e)[:70]}"]
    if not outcomes:
        return []
    mol = Chem.MolFromSmiles(smiles)
    left = add_atoms(atom_counts(mol), co_atoms)
    out = []
    for smi in outcomes[:4]:
        pm = Chem.MolFromSmiles(smi)
        if pm is None:
            out.append(f"产物无法解析 [{smi[:30]}]")
            continue
        right = add_atoms(dict(by_atoms), atom_counts(pm))
        d = atom_diff(left, right)
        out.append(("配平" if not d else f"失衡{d}") + f" [{rdMolDescriptors.CalcMolFormula(pm)}]")
    return out


CASES = [
    ("苯甲酸甲酯 / 链状酯",     "COC(=O)c1ccccc1",       {"H2O": 1}),
    ("乙酸乙酯 / 链状酯",       "CCOC(C)=O",             {"H2O": 1}),
    ("ε-己内酯 / 六元环内酯",   "O=C1CCCCCO1",           {"H2O": 1}),
    ("γ-丁内酯 / 五元环内酯",   "O=C1CCCO1",             {"H2O": 1}),
    ("香豆素 / 芳香环内酯",     "O=c1ccc2ccccc2o1",      {"H2O": 1}),
]

SMARTS_ORIG = "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"

print()
print("=" * 80)
print("1. 用「原 SMARTS（无 !@ 约束）」对比两条路线")
print("=" * 80)
for label, smi, co in CASES:
    print(f"\n【{label}】  {smi}")
    a = balance_rdkit(SMARTS_ORIG, smi, co=co)
    b = balance_rdchiral(SMARTS_ORIG, smi, co=co)
    print(f"   A rdkit原生 : {a if a else '不匹配'}")
    print(f"   B rdchiral  : {b if b else '不匹配'}")

print()
print("=" * 80)
print("2. 用「加了 !@ 的 SMARTS」再对比一次")
print("=" * 80)
SMARTS_NORING = "[C:1](=[O:2])[O:3]!@[C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"
for label, smi, co in CASES:
    print(f"\n【{label}】  {smi}")
    a = balance_rdkit(SMARTS_NORING, smi, co=co)
    b = balance_rdchiral(SMARTS_NORING, smi, co=co)
    print(f"   A rdkit原生 : {a if a else '不匹配'}")
    print(f"   B rdchiral  : {b if b else '不匹配'}")

print()
print("=" * 80)
print("3. 结论要点")
print("=" * 80)
print("""
关心的问题是：rdchiral 能不能在不加 !@ 约束的情况下，
正确处理"环内断键"，既给出正确产物、又不凭空造原子。
如果 B 列在环内酯上显示「配平」，那么环内断键就有通用解法。
""")
