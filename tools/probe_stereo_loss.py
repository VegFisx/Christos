# -*- coding: utf-8 -*-
r"""手工验证立体化学校验报的 4 条是不是真问题。

挑最干净的一例：1-[(1r)-4-methyl-1-cyclohex-3-enyl]ethanone，只有 1 个手性中心。
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
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

SMI = "CC(=O)[C@@H]1CC=C(C)C1"
print(f"底物: {SMI}")
m = Chem.MolFromSmiles(SMI)
Chem.AssignStereochemistry(m, cleanIt=True, force=True)
print(f"  手性中心: {Chem.FindMolChiralCenters(m, includeUnassigned=False)}")
print(f"  重原子数: {m.GetNumHeavyAtoms()}")

import json
rules = {r["id"]: r for r in json.loads(
    (STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]}

for rid in ("reduction_double_bond_001", "isomerization_double_bond_001"):
    r = rules.get(rid)
    if r is None:
        # 试别的 id
        cand = [x for x in rules.values() if x["name"] in ("双键加氢", "双键位置异构")]
        r = cand[0] if cand else None
    if r is None:
        continue
    print(f"\n【{r['name']}】{r['smarts']}")
    rxn = AllChem.ReactionFromSmarts(r["smarts"])
    patt = rxn.GetReactantTemplate(0)
    match = m.GetSubstructMatch(patt)
    mapped = [patt.GetAtomWithIdx(i).GetAtomMapNum() for i in range(patt.GetNumAtoms())]
    print(f"  模板原子数 {patt.GetNumAtoms()}  子结构匹配 {bool(match)}")
    print(f"  模板映射号: {mapped}")
    if match:
        touched = [match[i] for i in range(len(match))
                   if patt.GetAtomWithIdx(i).GetAtomMapNum()]
        print(f"  作用范围覆盖的底物原子 idx: {touched}")
        print(f"  底物手性中心 idx: "
              f"{[i for i, _t in Chem.FindMolChiralCenters(m, includeUnassigned=False)]}")

    res = rxn.RunReactants((m,))
    print(f"  产物组数: {len(res)}")
    for k, ps in enumerate(res[:2]):
        frags = []
        tot = 0
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
            except Exception as e:
                frags.append(f"(价态非法 {e})")
                continue
            cc = Chem.FindMolChiralCenters(pc, includeUnassigned=False)
            tot += len(cc)
            frags.append(f"{Chem.MolToSmiles(pc)}  手性={cc}")
        print(f"    组{k}: 合计手性 {tot}")
        for f in frags:
            print(f"       {f}")

print()
print("=" * 80)
print("判断")
print("=" * 80)
print("""
如果产物的 SMILES 里手性标记没了，但反应根本没碰那个碳，
说明 RDKit 在做这个转化时【丢了立体化学描述符】——这是真问题。

如果产物 SMILES 里手性标记还在（只是我的计数方式有偏差），那是误报。
""")
