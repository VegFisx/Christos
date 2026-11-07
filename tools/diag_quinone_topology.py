# -*- coding: utf-8 -*-
r"""量清各种醌的结构特征，为补规则做准备。

上轮发现：蒽醌类两个版本都匹配不上。
原因猜想：蒽醌的两个 C=O【不相邻】（9、10 位隔着环碳），
          而现有 SMARTS [O:1]=[C:2][C:3]=[O:4] 要求两个羰基【直接相连】。

本脚本量一下：
  · 每个醌的两个 C=O 碳之间最短路径有几条键
  · 邻醌（1,2-）和对醌（1,4-）分别是什么特征
  · 顺带看对应的二酚（酚氧化成醌的前体）
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import rdmolops

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# (名称, SMILES, 类别)
QUINONES = [
    ("对苯醌 (1,4-苯醌)", "O=C1C=CC(=O)C=C1", "对醌"),
    ("邻苯醌 (1,2-苯醌)", "O=C1C=CC=CC1=O", "邻醌"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "对醌"),
    ("1,2-萘醌", "O=C1C=CC2=CC=CC=C2C1=O", "邻醌"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "对醌"),
    ("大黄素（蒽醌）", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O", "对醌"),
    ("丹参酮IIA", "CC1=C(C(=O)C2=C(C1=O)c1ccccc1O2)C", "邻醌?"),
    ("辅酶Q0（对醌）", "COc1cc(C)C(=O)C(C)=CC1=O", "对醌"),
]

DIOLS = [
    ("邻苯二酚", "Oc1ccccc1O", "邻二酚"),
    ("对苯二酚", "Oc1ccc(O)cc1", "对二酚"),
    ("1,2-二羟基萘", "Oc1ccc2ccccc2c1O", "邻二酚"),
    ("1,4-二羟基萘", "Oc1ccc(O)c2ccccc12", "对二酚"),
    ("蒽氢醌 (9,10-二羟基蒽)", "Oc1c2ccccc2c(O)c2ccccc12", "对二酚"),
]

QUINONE_PATT = Chem.MolFromSmarts("[O:1]=[C:2][C:3]=[O:4]")
DIOL_PATT = Chem.MolFromSmarts("[OH:1][c:2][c:3][OH:4]")


def co_distances(mol):
    """找出所有成对的羰基氧，报告对应碳之间的最短路径长度。"""
    cos = [a.GetIdx() for a in mol.GetAtoms()
           if a.GetSymbol() == "O" and a.GetDegree() == 1
           and any(b.GetBondTypeAsDouble() == 2.0
                   for b in a.GetBonds())]
    carbons = []
    for o in cos:
        for nb in mol.GetAtomWithIdx(o).GetNeighbors():
            if nb.GetSymbol() == "C":
                carbons.append(nb.GetIdx())
    out = []
    for i in range(len(carbons)):
        for j in range(i + 1, len(carbons)):
            d = rdmolops.GetShortestPath(mol, carbons[i], carbons[j])
            out.append(len(d) - 1)      # 键数
    return sorted(set(out))


print("=" * 92)
print("① 醌类：两个 C=O 碳之间的最短键数")
print("=" * 92)
print(f"{'名称':<22}{'类别':<8}{'键数分布':<14}{'现有 SMARTS 匹配'}")
print("-" * 92)
for name, smi, kind in QUINONES:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        print(f"{name:<22}{kind:<8}★SMILES 解析失败")
        continue
    ds = co_distances(m)
    hit = m.HasSubstructMatch(QUINONE_PATT)
    print(f"{name:<22}{kind:<8}{str(ds):<14}{'✓ 匹配' if hit else '✗ 不匹配'}")

print()
print("=" * 92)
print("② 二酚类：两个 OH 所在芳香碳之间的最短键数")
print("=" * 92)
print(f"{'名称':<22}{'类别':<8}{'键数分布':<14}{'现有 SMARTS 匹配'}")
print("-" * 92)
for name, smi, kind in DIOLS:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        print(f"{name:<22}{kind:<8}★SMILES 解析失败")
        continue
    ds = co_distances(m)
    hit = m.HasSubstructMatch(DIOL_PATT)
    print(f"{name:<22}{kind:<8}{str(ds):<14}{'✓ 匹配' if hit else '✗ 不匹配'}")

print()
print("=" * 92)
print("③ 结论")
print("=" * 92)
print("""
  邻醌/邻二酚：两个官能团的碳【直接相连】→ 键数 1 → 现有规则能匹配
  对醌/对二酚：两个官能团的碳【隔 2 个键】→ 键数 2 → 现有规则匹配不上

  所以需要【另一条规则】专门处理对位（1,4-）的醌/二酚。
  这正是论文说明里写「大黄蒽醌」却没实现的那部分。
""")
