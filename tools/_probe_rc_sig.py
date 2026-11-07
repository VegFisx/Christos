# -*- coding: utf-8 -*-
r"""一次性探针：能不能从反应 SMARTS 抽出**可比较的反应中心签名**？"""
from __future__ import annotations

import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")


def side_sig(mol) -> tuple:
    r"""映射原子签名：((map, 原子序数, 形式电荷, 重原子度), ...) + 映射原子间的键。"""
    atoms, bonds = [], []
    if mol is None:
        return ()
    for a in mol.GetAtoms():
        am = a.GetAtomMapNum()
        if not am:
            continue
        atoms.append((am, a.GetAtomicNum(), a.GetFormalCharge(),
                      sum(1 for b in a.GetBonds() if b.GetOtherAtom(a).GetAtomicNum() > 1)))
    idx2map = {a.GetIdx(): a.GetAtomMapNum() for a in mol.GetAtoms() if a.GetAtomMapNum()}
    for b in mol.GetBonds():
        m1, m2 = idx2map.get(b.GetBeginAtomIdx()), idx2map.get(b.GetEndAtomIdx())
        if m1 and m2:
            bonds.append(tuple(sorted((m1, m2))) + (str(b.GetBondType()),))
    return (tuple(sorted(atoms)), tuple(sorted(bonds)))


def rc_sig(smarts: str):
    rxn = AllChem.ReactionFromSmarts(smarts)
    if rxn is None:
        return None
    r = [side_sig(rxn.GetReactantTemplate(i)) for i in range(rxn.GetNumReactantTemplates())]
    p = [side_sig(rxn.GetProductTemplate(i)) for i in range(rxn.GetNumProductTemplates())]
    return (tuple(sorted(r)), tuple(sorted(p)))


R = json.loads(open(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json",
                    encoding="utf-8").read())
rs = R if isinstance(R, list) else R.get("rules")
print("规则样例签名：")
for x in rs[:3]:
    s = rc_sig(x["smarts"])
    print("  %-28s %s" % (x["id"], str(s)[:160]))
print()
mined = []
with open(r"D:\ProgramData\DSHNS\chemreact-staging\reports\mined_forward_templates_full_lf.jsonl",
          encoding="utf-8") as fh:
    for ln in fh:
        if ln.strip():
            mined.append(json.loads(ln))
        if len(mined) >= 3:
            break
print("挖掘模板样例签名：")
for d in mined:
    print("  %-40s %s" % (d["template"][:40], str(rc_sig(d["template"]))[:160]))
