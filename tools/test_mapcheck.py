import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\rules")
from rdkit.Chem import AllChem
from schema import _check_atom_maps

CASES = [
    ("原始坏写法：产物 [O:3] 但反应物里 3 是氮", "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[O:3][H].[N:3][C:4]"),
    ("我上一轮的坏写法：新氧编号 [O:5]",        "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[O:5][H].[N:3][C:4]"),
    ("胺氧化坏写法：反应物 [N:2] vs 产物 [O:2]", "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O:2].[NH3]"),
    ("修好之后：新氧不编号 [OH]",               "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[OH].[N:3][C:4]"),
    ("修好之后：新氧不编号 [O]",                "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O].[N:2]"),
    ("正常规则：酯水解（对照）",                 "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"),
]
print(f"{'情形':<44}{'检出问题数':>10}")
print("-" * 78)
for label, smarts in CASES:
    rxn = AllChem.ReactionFromSmarts(smarts)
    probs = _check_atom_maps(rxn)
    print(f"{label:<44}{len(probs):>10}")
    for p in probs:
        print(f"      → {p[:110]}")
