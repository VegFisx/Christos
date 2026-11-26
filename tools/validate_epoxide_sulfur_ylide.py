# -*- coding: utf-8 -*-
"""专用验证：cyclization_epoxide_sulfur_ylide_001。"""
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

RID = "cyclization_epoxide_sulfur_ylide_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = "uspto50k_test_US08497294B2"
POS = ("C[S+](C)C", "O=C(c1ccccc1)c1ccccc1",
       "C1OC1(c2ccccc2)c2ccccc2")
NEG = [
    ("benzophenone+dimethyl sulfide", "O=C(c1ccccc1)c1ccccc1", "CSC"),
    ("benzaldehyde+ylide", "O=Cc1ccccc1", "C[S+](C)C"),
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
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", f):
        out[e] += float(n or 1)
    return out


def balance(reactants, product):
    left = Counter()
    for s in list(reactants) + ["[OH-]"]:
        m = Chem.MolFromSmiles(s)
        if m is None:
            return False
        for k, v in fcount(rdMolDescriptors.CalcMolFormula(m)).items():
            left[k] += v
    m = Chem.MolFromSmiles(product)
    if m is None:
        return False
    right = fcount(rdMolDescriptors.CalcMolFormula(m))
    for f, n in (("C2H6S", 1), ("H2O", 1)):
        for k, v in fcount(f).items():
            right[k] += v * n
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

    prods, hit = run(POS[:2], POS[2])
    ok = bool(hit) and balance(POS[:2], POS[2])
    print("%-4s POS standard products=%d balance=%s" %
          ("PASS" if ok else "FAIL", len(prods), balance(POS[:2], POS[2])))
    fails += 0 if ok else 1

    c = BY[EXTERNAL]
    prods, hit = run(c["reactants"], c["product"])
    ok = bool(hit) and balance(c["reactants"], c["product"])
    print("%-4s EXT %s products=%d balance=%s" %
          ("PASS" if ok else "FAIL", EXTERNAL, len(prods),
           balance(c["reactants"], c["product"])))
    fails += 0 if ok else 1

    for name, a, b in NEG:
        prods, hit = run([a, b], POS[2])
        ok = not prods
        print("%-4s NEG %-28s products=%d" % ("PASS" if ok else "FAIL", name, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
