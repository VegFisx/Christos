# -*- coding: utf-8 -*-
"""专用验证：cyclization_indole_alkynylaniline_001。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdMolDescriptors

import templates as T
from engine import Compound
from smartreact_engine import SmartReactEngine

RID = "cyclization_indole_alkynylaniline_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = "uspto50k_test_US20110071150A1"
STD = ("Nc1ccccc1C#Cc1ccccc1", "c1ccc2[nH]c(-c3ccccc3)cc2c1")
NEG = ["Nc1ccccc1C#N", "Nc1ccccc1C=C"]


def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def formula(s):
    m = Chem.MolFromSmiles(s or "")
    return rdMolDescriptors.CalcMolFormula(m) if m else ""


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=[RID],
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("煎煮")
    fails = 0
    print(eng.curated_note)

    def run(smi, target):
        prods = eng.step([Compound(smiles=smi, name="x", herb="test")],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        return prods, [p for p in prods if key(getattr(p, "smiles", "")) == want]

    prods, hit = run(STD[0], STD[1])
    ok = bool(hit) and formula(STD[0]) == formula(STD[1])
    print("%-4s STD products=%d formula_same=%s"
          % ("PASS" if ok else "FAIL", len(prods), formula(STD[0]) == formula(STD[1])))
    fails += 0 if ok else 1

    c = BY[EXTERNAL]
    prods, hit = run(c["reactants"][0], c["product"])
    ok = bool(hit) and formula(c["reactants"][0]) == formula(c["product"])
    print("%-4s EXT %s products=%d formula_same=%s"
          % ("PASS" if ok else "FAIL", EXTERNAL, len(prods),
             formula(c["reactants"][0]) == formula(c["product"])))
    fails += 0 if ok else 1

    for smi in NEG:
        prods, _hit = run(smi, STD[1])
        ok = not prods
        print("%-4s NEG %-20s products=%d" % ("PASS" if ok else "FAIL", smi, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
