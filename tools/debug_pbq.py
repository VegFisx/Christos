# -*- coding: utf-8 -*-
"""查对苯醌为什么连反应物模板都匹配不上。"""
from rdkit import Chem

m = Chem.MolFromSmiles("O=C1C=CC(=O)C=C1")
print("对苯醌:", Chem.MolToSmiles(m), " 重原子:", m.GetNumAtoms())
for a in m.GetAtoms():
    nb = [(b.GetOtherAtomIdx(a.GetIdx()), str(b.GetBondType())) for b in a.GetBonds()]
    print(f"  idx{a.GetIdx()} {a.GetSymbol()} 芳香={a.GetIsAromatic()} 邻居={nb}")

print()
PATS = [
    "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]",
    "[O:1]=[C:2][C:5][C:6][C:3]=[O:4]",
    "[O]=[C][C][C][C]=[O]",
    "[O:1]=[C:2][#6:5][C:3]=[O:4]",
    "[O:1]=[C:2][#6:5][#6:6][#6:7][C:3]=[O:4]",
]
for pat in PATS:
    q = Chem.MolFromSmarts(pat)
    if q is None:
        print(f"{pat:<48} ★SMARTS 编译失败")
        continue
    ms = m.GetSubstructMatches(q)
    print(f"{pat:<48} 匹配 {len(ms)}  {ms}")

print()
print("对照：1,4-萘醌")
n = Chem.MolFromSmiles("O=C1C=CC(=O)c2ccccc21")
for pat in PATS[:2]:
    q = Chem.MolFromSmarts(pat)
    ms = n.GetSubstructMatches(q)
    print(f"  {pat:<46} 匹配 {len(ms)}")
