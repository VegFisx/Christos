# -*- coding: utf-8 -*-
r"""查「脱水」那条立体化学标记——从第 15 轮挂到现在。

上轮（15 轮）的情况：
    规则报"2/236 例丢失作用范围外的旁观手性中心"
    例：(12r,12''r)-diheraclenol
    手工复验时发现我的旁观者判定在某类 SMARTS 上可能有偏差
    （曾出现"模板原子数=0 却仍被标记"）

本脚本把那一例彻底跑清楚。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants

import json
data = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
r = next(x for x in data["rules"] if x["id"] == "elimination_dehydration_001")
SM = r["smarts"]
print("脱水 SMARTS:", SM)
print()

SUB = ("CC(C)([C@@H](COC1=C2C(=CC3=C1OC=C3)C=CC(=O)O2)O)"
       "OC(C)(C)[C@H](COC4=C5C(=CC6=C4OC=C6)C=CC(=O)O5)O")
m = Chem.MolFromSmiles(SUB)
Chem.AssignStereochemistry(m, cleanIt=True, force=True)
centers = Chem.FindMolChiralCenters(m, includeUnassigned=False)
print(f"底物重原子 {m.GetNumAtoms()}  手性中心 {centers}")

rxn = AllChem.ReactionFromSmarts(SM)
patt = rxn.GetReactantTemplate(0)
print(f"反应物模板原子数: {patt.GetNumAtoms()}")
print(f"模板 SMARTS: {Chem.MolToSmarts(patt)}")
ms = m.GetSubstructMatches(patt)
print(f"底物匹配位点: {len(ms)}  {ms}")

if ms:
    match = ms[0]
    mapped = [i for i in range(patt.GetNumAtoms())
              if patt.GetAtomWithIdx(i).GetAtomMapNum()]
    touched = sorted(match[i] for i in mapped)
    spec = {i for i, _t in centers}
    spec_set = sorted(spec)
    print(f"\n模板里带映射号的原子下标: {mapped}")
    print(f"→ 覆盖的底物原子: {touched}")
    print(f"底物手性中心: {spec_set}")
    print(f"旁观者（不在作用范围内）: {sorted(spec - set(touched))}")

print()
print("rdchiral 产物:")
outs = rdchiralRun(rdchiralReaction(SM), rdchiralReactants(SUB)) or []
print(f"  {len(outs)} 个")
for o in outs[:3]:
    tot = 0
    parts = []
    for part in o.split("."):
        pm = Chem.MolFromSmiles(part)
        if pm is None:
            parts.append(f"{part[:30]} (解析失败)")
            continue
        cc = Chem.FindMolChiralCenters(pm, includeUnassigned=False)
        tot += len(cc)
        parts.append(f"{part[:40]} 手性={cc}")
    print(f"    合计手性 {tot}")
    for p in parts:
        print(f"      {p}")

print()
print("rdkit 产物:")
res = rxn.RunReactants((m,))
print(f"  {len(res)} 组")
for ps in res[:2]:
    tot = 0
    for p in ps:
        pc = Chem.Mol(p)
        try:
            Chem.SanitizeMol(pc)
            pc = Chem.RemoveHs(pc)
        except Exception as e:
            print(f"    (价态非法 {str(e)[:30]})")
            continue
        cc = Chem.FindMolChiralCenters(pc, includeUnassigned=False)
        tot += len(cc)
        print(f"    {Chem.MolToSmiles(pc)[:56]} 手性={cc}")
    print(f"    → 合计手性 {tot}")
