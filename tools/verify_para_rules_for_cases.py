# -*- coding: utf-8 -*-
r"""验证两条对醌规则的期望产物，确认后再写进验收套件。

★ 上一轮的教训：手写复杂 SMILES 会错。
   所以这次先把引擎实际产出的东西打出来，用它来写期望。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")
from engine import Compound, load_engine
import templates as T

# ★ 第七十五轮 H3：能查到的那几个底物改成**从 tcm.db 取**（InChIKey 引用 / 只读）；
#   查不到的（蒽氢醌、大黄素型蒽酚）如实留字面量并标 why。
sys.path.insert(0, str(Path(__file__).resolve().parent))
import case_db

eng, rules, profs = load_engine()
by_id = {r["id"]: r for r in rules}


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


CASES = [
    ("对二酚氧化成醌", "oxidation_diphenol_para_001", "氧化",
     [("对苯二酚", {"db": "QIGBRXMKCJKVMJ-UHFFFAOYSA-N", "name": "Hydroquinone"}),
      ("9,10-蒽氢醌", {"lit": "Oc1c2ccccc2c(O)c2ccccc12", "why": "库外（tcm.db 没有）"}),
      ("大黄素型蒽酚", {"lit": "Cc1cc(O)c2c(c1)C(O)c1c(C2O)c(O)cc(O)c1O",
                    "why": "库外（tcm.db 没有）"})]),
    ("对醌还原成二酚", "reduction_quinone_para_001", "还原",
     [("对苯醌", {"db": "AZQWKYJCGOJGHM-UHFFFAOYSA-N", "name": "P-quinone"}),
      ("9,10-蒽醌", {"db": "RZVHIXYEVGDQDX-UHFFFAOYSA-N", "name": "Morkit"}),
      ("大黄素", {"lit": "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O",
                "why": "库外（tcm.db 没有）"})]),
]

for rname, rid, cond_name, subs in CASES:
    r = by_id.get(rid)
    if r is None:
        print(f"  ✗ 找不到规则 {rid}")
        continue
    cond = T.get_template(cond_name)
    print("=" * 100)
    print(f"【{rname}】{rid}   工艺 {cond_name}")
    print("=" * 100)
    for nm, ref in subs:
        smi = case_db.resolve(ref)
        s = Compound(smiles=smi, name=nm, herb="t")
        ps = eng.apply_rule(r, s, 0.8, 1, cond)
        print(f"\n  底物 {nm}  ({smi})  [{case_db.describe(ref)}]")
        print(f"      分子式 {Chem.rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(smi))}")
        if not ps:
            print("      → 0 个产物 ★需要检查★")
        for p in ps[:4]:
            print(f"      → {p.formula:<14}{p.smiles}")
            print(f"          规范化 {canon(p.smiles)}")
    print()
