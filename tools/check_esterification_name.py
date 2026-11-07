# -*- coding: utf-8 -*-
"""查论文【酯化】与我库里哪条规则对应（名字不同导致的假"缺失"）。"""
import csv
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")

paper = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()

rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

print("论文里的【酯化】:")
print("   ", paper.get("酯化"))
print()
print("我库里所有名字含「酯」的规则:")
for r in rules:
    if "酯" in r["name"]:
        print(f"    {r['name']:<20}{r['id']}")
        print(f"        {r['smarts']}")

print()
p = paper.get("酯化", "")
print("与论文【酯化】SMARTS 完全相同的我库规则:")
hit = [r for r in rules if r["smarts"].strip() == p]
if hit:
    for r in hit:
        print(f"    ★ {r['name']}  ({r['id']})")
else:
    print("    （无）")
    print()
    print("论文【酯化】有几个反应物模板？")
    from rdkit.Chem import AllChem
    try:
        rxn = AllChem.ReactionFromSmarts(p)
        print(f"    {rxn.GetNumReactantTemplates()} 个")
    except Exception as e:
        print(f"    编译失败: {e}")

print()
print("我库里所有 esterification 类规则:")
for r in rules:
    if r.get("category") == "esterification":
        print(f"    {r['name']:<20}{r['id']}")
