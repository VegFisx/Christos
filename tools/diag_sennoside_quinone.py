# -*- coding: utf-8 -*-
r"""查：番泻苷 e 为什么在「醌还原」上匹配不上我的规则？

番泻苷 e 来自大黄，是二蒽酮苷 —— 中药里真实且重要的成分。
论文版 SMARTS 能产，我的不能，这可能是回归。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

# 我有哪些"醌"相关的规则
print("=" * 96)
print("① 我库里所有「醌」相关规则")
print("=" * 96)
for r in rules:
    if "醌" in r["name"] or "quinone" in r["id"]:
        print(f"  【{r['name']}】{r['id']}  status={r.get('status')}")
        print(f"      {r['smarts']}")

# 论文版
import csv
paper = {}
with (Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")).open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()
print()
print("=" * 96)
print("② 论文版「醌还原」")
print("=" * 96)
for k in paper:
    if "醌" in k:
        print(f"  【{k}】")
        print(f"      {paper[k]}")

# 番泻苷 e
SEN = ("O=C(O)c1cc(O)c2c(c1)[C@H]([C@H]1c3cc(C(=O)O)cc(O)c3C(=O)"
       "c3c(O[C@@H]4O[C@H](COC(O)C(O)O)[C@@H](O)[C@H](O)[C@H]4O)cccc31)"
       "c1cccc(O[C@@H]3O[C@H](CO)[C@@H](O)[C@H](O)[C@H]3O)c1C2=O")
m = Chem.MolFromSmiles(SEN)
print()
print("=" * 96)
print("③ 番泻苷 e 的匹配情况")
print("=" * 96)
print(f"  重原子 {m.GetNumHeavyAtoms() if m else '解析失败'}")
ri = m.GetRingInfo()
n6 = sum(1 for ring in ri.AtomRings() if len(ring) == 6)
print(f"  六元环 {n6} 个，总环 {len(ri.AtomRings())} 个")

for r in rules:
    if "醌" not in r["name"] and "quinone" not in r["id"]:
        continue
    try:
        rxn = AllChem.ReactionFromSmarts(r["smarts"])
    except Exception as ex:
        print(f"  【{r['name']}】编译失败 {ex}")
        continue
    patt = rxn.GetReactantTemplate(0)
    ms = m.GetSubstructMatches(patt)
    print(f"  【{r['name']}】模板 {Chem.MolToSmarts(patt)[:60]}")
    print(f"      匹配 {len(ms)} 处")
    try:
        res = rxn.RunReactants((m,))
        print(f"      产物 {len(res)} 组")
    except Exception as ex:
        print(f"      运行异常 {str(ex)[:60]}")

print()
print("=" * 96)
print("④ 论文版醌还原在同一个底物上")
print("=" * 96)
for k, sm in paper.items():
    if "醌" not in k:
        continue
    try:
        rxn = AllChem.ReactionFromSmarts(sm)
        patt = rxn.GetReactantTemplate(0)
        ms = m.GetSubstructMatches(patt)
        print(f"  【{k}】{sm[:60]}")
        print(f"      匹配 {len(ms)} 处")
        res = rxn.RunReactants((m,))
        print(f"      产物 {len(res)} 组")
    except Exception as ex:
        print(f"  【{k}】异常 {str(ex)[:60]}")

print()
print("=" * 96)
print("⑤ 番泻苷里的 C=O 碳：彼此相距几个键？")
print("=" * 96)
cos = []
for a in m.GetAtoms():
    if a.GetSymbol() == "C":
        for nb in a.GetNeighbors():
            if nb.GetSymbol() == "O" and m.GetBondBetweenAtoms(a.GetIdx(), nb.GetIdx()).GetBondTypeAsDouble() == 2.0:
                cos.append((a.GetIdx(), nb.GetIdx()))
                break
print(f"  C=O 碳 {len(cos)} 个: {[c[0] for c in cos]}")
if len(cos) >= 2:
    from rdkit.Chem import rdmolops
    for i in range(len(cos)):
        for j in range(i + 1, len(cos)):
            p = rdmolops.GetShortestPath(m, cos[i][0], cos[j][0])
            if len(p) - 1 <= 3:
                ring = [r for r in ri.AtomRings() if cos[i][0] in r and cos[j][0] in r]
                print(f"      idx{cos[i][0]} ↔ idx{cos[j][0]}: "
                      f"{len(p)-1} 键   同一环: {'是' if ring else '否'}")
