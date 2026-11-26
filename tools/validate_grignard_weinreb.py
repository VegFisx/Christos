# -*- coding: utf-8 -*-
"""专用验证：格氏试剂对酮/Weinreb 酰胺的加成（两条规则）。"""
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

RIDS = ["addition_grignard_ketone_001", "addition_grignard_weinreb_001"]
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}


def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def ftext(f):
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", str(f or "")):
        out[e] += int(n or 1)
    return out


def fc(s):
    m = Chem.MolFromSmiles(s)
    return ftext(rdMolDescriptors.CalcMolFormula(m)) if m else ftext(s)


def balance(left, target, byproducts):
    l = Counter()
    for s in list(left) + ["[Cl-]", "O"]:
        l += fc(s)
    r = fc(target)
    for s in byproducts:
        r += ftext(s)
    return all(abs(l.get(k, 0) - r.get(k, 0)) < 1e-6
               for k in set(l) | set(r))


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=RIDS,
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("室温浸泡")
    fails = 0
    print(eng.curated_note)

    def run(reactants, target, byproducts):
        prods = eng.step([Compound(smiles=s, name="x", herb="test")
                          for s in reactants], cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit, balance(reactants, target, byproducts)

    tests = [
        ("KET std", ["CC(=O)C", "C[Mg+]"], "CC(C)(C)O", ["ClHMgO"]),
        ("KET std rev", ["C[Mg+]", "CC(=O)C"], "CC(C)(C)O", ["ClHMgO"]),
        ("KET ext", ["O=C1c2ccccc2-c2ccccc21", "Cc1ccc[c]([Mg+])c1"],
         BY["uspto50k_test_US06162824"]["product"], ["ClHMgO"]),
        ("KET ext rev", ["Cc1ccc[c]([Mg+])c1", "O=C1c2ccccc2-c2ccccc21"],
         BY["uspto50k_test_US06162824"]["product"], ["ClHMgO"]),
        ("WEIN std", ["CON(C)C(=O)c1ccccc1", "C[Mg+]"],
         "CC(=O)c1ccccc1", ["C2H7NO", "ClHMgO"]),
        ("WEIN std rev", ["C[Mg+]", "CON(C)C(=O)c1ccccc1"],
         "CC(=O)c1ccccc1", ["C2H7NO", "ClHMgO"]),
    ]
    for cid in ("uspto50k_test_US05607956", "uspto50k_test_US08501732B2"):
        c = BY[cid]
        tests.append(("WEIN " + cid[-6:], list(c["reactants"]), c["product"],
                      ["C2H7NO", "ClHMgO"]))
        tests.append(("WEIN rev " + cid[-6:], list(reversed(c["reactants"])),
                      c["product"], ["C2H7NO", "ClHMgO"]))

    for label, reactants, target, byp in tests:
        prods, hit, bal = run(reactants, target, byp)
        ok = bool(hit) and bal
        print("%-4s %-20s products=%d hit=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit), bal))
        fails += 0 if ok else 1

    for label, reactants in (
            ("no Mg ketone", ["CC(=O)C", "CCO"]),
            ("no Mg amide", ["CON(C)C(=O)c1ccccc1", "CCO"])):
        prods, _hit, _bal = run(reactants, "CC(C)(C)O", ["ClHMgO"])
        ok = not prods
        print("%-4s NEG %-20s products=%d" % ("PASS" if ok else "FAIL", label, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
