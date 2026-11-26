# -*- coding: utf-8 -*-
"""专用验证：cyclization_oxadiazole_diacylhydrazine_001。"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
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

RID = "cyclization_oxadiazole_diacylhydrazine_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = "uspto50k_test_US20100041892A1"
POS = [
    ("aryl/alkyl", "CC(=O)NNC(=O)c1ccccc1", "Cc1nnc(-c2ccccc2)o1"),
    ("dialkyl", "CC(=O)NNC(=O)C", "Cc1nnc(C)o1"),
]
NEG = [
    ("monoacylhydrazide", "CC(=O)NNC"),
    ("amide", "CC(=O)NC"),
]


def key(s):
    m = Chem.MolFromSmiles(s or "")
    if m is None:
        return ""
    try:
        from rdkit.Chem import inchi
        return inchi.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def fcount(f):
    f = (f or "").replace("+", "").replace("-", "")
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", f):
        out[e] += int(n or 1)
    return out


def balance(reactants, product):
    left = Counter()
    for s in reactants:
        m = Chem.MolFromSmiles(s)
        if m is None:
            return False
        left += fcount(rdMolDescriptors.CalcMolFormula(m))
    m = Chem.MolFromSmiles(product)
    if m is None:
        return False
    right = fcount(rdMolDescriptors.CalcMolFormula(m))
    for k, v in fcount("H2O").items():
        right[k] += v
    return all(abs(left.get(k, 0) - right.get(k, 0)) < 1e-6
               for k in set(left) | set(right))


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

    def run(reactants, target):
        prods = eng.step([Compound(smiles=s, name="x", herb="test") for s in reactants],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        return prods, [p for p in prods if key(getattr(p, "smiles", "")) == want]

    for label, smi, target in POS:
        prods, hit = run([smi], target)
        ok = bool(hit) and balance([smi], target)
        print("%-4s POS %-14s products=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), balance([smi], target)))
        fails += 0 if ok else 1

    c = BY[EXTERNAL]
    prods, hit = run(c["reactants"], c["product"])
    ok = bool(hit) and balance(c["reactants"], c["product"])
    print("%-4s EXT %s products=%d balance=%s"
          % ("PASS" if ok else "FAIL", EXTERNAL, len(prods),
             balance(c["reactants"], c["product"])))
    fails += 0 if ok else 1

    for label, smi in NEG:
        prods, _hit = run([smi], "Cc1nnc(C)o1")
        ok = not prods
        print("%-4s NEG %-20s products=%d" % ("PASS" if ok else "FAIL", label, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
