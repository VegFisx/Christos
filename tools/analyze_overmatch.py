# -*- coding: utf-8 -*-
r"""看清「对醌还原」过度匹配的那个环状 1,3-二酮，找出可区分的结构特征。

底物：22-dihydrostigmast-4-en-3,6-dione
      CC[C@H](CC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(CC[C@H]3[C@@H]2CC(=O)C4[C@]3(CCC(=O)C4)C)C)C(C)C

要看清：
  · 匹配到的四个原子分别是哪几个
  · 两个 C=O 碳之间的路径有多长
  · 和真醌（对苯醌/蒽醌）相比，结构上到底差在哪
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdmolops

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

PATT = Chem.MolFromSmarts("[O:1]=[C;r6:2]~[#6;R:5]~[#6;R:6]~[C;r6:3]=[O:4]")

CASES = [
    ("对苯醌（真醌）", "O=C1C=CC(=O)C=C1"),
    ("9,10-蒽醌（真醌）", "O=C1c2ccccc2C(=O)c2ccccc21"),
    ("甾体3,6-二酮（过度匹配）",
     "CC[C@H](CC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(CC[C@H]3[C@@H]2CC(=O)C4[C@]3(CCC(=O)C4)C)C)C(C)C"),
]

for name, smi in CASES:
    m = Chem.MolFromSmiles(smi)
    print(f"\n{'=' * 96}\n【{name}】重原子 {m.GetNumAtoms()}\n{'=' * 96}")
    ms = m.GetSubstructMatches(PATT)
    print(f"  匹配位点数: {len(ms)}")
    for k, match in enumerate(ms[:3]):
        o1, c2, c5, c6, c3, o4 = match
        print(f"\n  第{k+1}个匹配:")
        print(f"    O1=idx{o1}  C2=idx{c2}  (桥)idx{c5}  (桥)idx{c6}  C3=idx{c3}  O4=idx{o4}")
        # 两个 C=O 碳之间的最短路径
        path = rdmolops.GetShortestPath(m, c2, c3)
        print(f"    C2→C3 最短路径长度: {len(path)-1} 个键, 经过 {len(path)-2} 个中间原子")
        print(f"      路径: {list(path)}")
        print(f"    匹配用的桥梁: idx{c5}, idx{c6}")
        # 环信息
        ri = m.GetRingInfo()
        rings_c2 = [r for r in ri.AtomRings() if c2 in r]
        rings_c3 = [r for r in ri.AtomRings() if c3 in r]
        print(f"    C2 所在环: {[len(r) for r in rings_c2]} 元 × {len(rings_c2)}")
        print(f"    C3 所在环: {[len(r) for r in rings_c3]} 元 × {len(rings_c3)}")
        same = [set(r) for r in rings_c2 if any(set(r) == set(s) for s in rings_c3)]
        print(f"    两碳共处的环: {'有' if same else '★无（不在同一个环里）★'}")
        # 两碳是否共同邻居
        nb2 = {n.GetIdx() for n in m.GetAtomWithIdx(c2).GetNeighbors()}
        nb3 = {n.GetIdx() for n in m.GetAtomWithIdx(c3).GetNeighbors()}
        print(f"    C2/C3 的共同邻居: {sorted(nb2 & nb3)}")
