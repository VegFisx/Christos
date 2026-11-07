# -*- coding: utf-8 -*-
"""验证论文【酯化】SMARTS 到底生成几元环，以及它在真实底物上能匹配到什么。"""
import csv
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
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")
paper = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()

SM = paper["酯化"]
print("论文【酯化】SMARTS:")
print("   ", SM)
rxn = AllChem.ReactionFromSmarts(SM)
patt = rxn.GetReactantTemplate(0)
print(f"    反应物模板 {rxn.GetNumReactantTemplates()} 个")
print(f"    模板原子数 {patt.GetNumAtoms()}")

# 用最小的 α-羟基酸试
TESTS = [
    ("乙醇酸 HOCH2COOH", "OCC(=O)O"),
    ("乳酸 CH3CH(OH)COOH", "CC(O)C(=O)O"),
    ("水杨酸（羟基在芳环）", "O=C(O)c1ccccc1O"),
    ("3-羟基丙酸", "OCCC(=O)O"),
    ("4-羟基丁酸（γ）", "OCCCC(=O)O"),
]
print()
print("=" * 96)
print("在不同羟基酸上的表现")
print("=" * 96)
for nm, smi in TESTS:
    m = Chem.MolFromSmiles(smi)
    ms = m.GetSubstructMatches(patt)
    res = rxn.RunReactants((m,)) if ms else []
    print(f"\n  {nm:<24}{smi}")
    print(f"      匹配 {len(ms)} 处，产物 {len(res)} 组")
    for ps in res[:2]:
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                pc = Chem.RemoveHs(pc)
                ri = pc.GetRingInfo()
                rings = [len(r) for r in ri.AtomRings()]
                print(f"          {Chem.MolToSmiles(pc):<40}环大小 {rings}")
            except Exception as e:
                print(f"          (价态非法 {str(e)[:40]})")

print()
print("=" * 96)
print("在真实药材成分上能匹配多少")
print("=" * 96)
tot = 0
hits = []
for herb in ("甘草", "附子", "干姜", "大黄" if True else ""):
    if not herb:
        continue
    rows = find_compounds(herb, limit=150)
    n = 0
    for rr in rows:
        m = Chem.MolFromSmiles(rr.get("smiles") or "")
        if m is None:
            continue
        if m.HasSubstructMatch(patt):
            n += 1
            if len(hits) < 6:
                hits.append((herb, rr.get("name"), rr.get("smiles")))
    print(f"  {herb}: {n} / {len(rows)} 个成分匹配")
    tot += n
print(f"\n  合计 {tot} 个真实成分能匹配")
for h, nm, smi in hits:
    print(f"      [{h}] {str(nm)[:34]:<36}{str(smi)[:44]}")
