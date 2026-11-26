# -*- coding: utf-8 -*-
"""Regression tests for the same-molecule (intramolecular) pair mode."""
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
for p in (ROOT / "libs", ROOT / "core", ROOT / "tools", ROOT / "sources", ROOT / "conditions"):
    sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions

RULES = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
RULE = next(r for r in RULES if r["id"] == "cyclization_macro_lactam_001")
RX = rdChemReactions.ReactionFromSmarts(RULE["smarts"])
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
EXT = next(c for c in CASES if c["id"] == "uspto50k_test_US20080070885A1")

STD_SMI = "CNC(=O)C(C)CC(O)C(Cc1cccc(OCCCCCC(=O)O)c1)NC(=O)C(C)[NH3+]"
STD_PROD = "CNC(=O)C(C)CC(O)C1Cc2cccc(c2)OCCCCCC(=O)NC(C)C(=O)N1"

PASS, FAIL = [], []

def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""

def check(label, got, want):
    (PASS if got == want else FAIL).append((label, got, want))

def main():
    from smartreact_engine import _apply_intra_pair

    std = _apply_intra_pair(RX, Chem.MolFromSmiles(STD_SMI), min_path=8)
    check("std skeleton", any(key(f) == key(STD_PROD) for g in std for f in g.split(".")), True)

    ext = _apply_intra_pair(RX, Chem.MolFromSmiles(EXT["reactants"][0]), min_path=8)
    check("held-out skeleton", any(key(f) == key(EXT["product"]) for g in ext for f in g.split(".")), True)

    short = _apply_intra_pair(RX, Chem.MolFromSmiles("NCCCC(=O)O"), min_path=8)
    check("short chain skipped", short, set())

    # The same rule must also work through the simple core Engine.apply_rule path.
    from engine import Compound, load_engine
    eng, rules, _profiles = load_engine()
    rule = next(r for r in rules if r["id"] == RULE["id"])
    prods = eng.apply_rule(rule, Compound(smiles=STD_SMI, name="std", herb="test"),
                           1.0, 1, None)
    check("core apply_rule", any(p.smiles == STD_PROD for p in prods), True)

    # Products returned by the helper must be sanitizable and non-empty.
    for g in list(std) + list(ext):
        for f in g.split("."):
            check("sanitizable:" + f[:24], Chem.MolFromSmiles(f) is not None, True)

    print("=" * 72)
    for label, got, want in PASS:
        print("PASS", label)
    for label, got, want in FAIL:
        print("FAIL", label, "got=", got, "want=", want)
    print("=" * 72)
    print("RESULT %d/%d PASS" % (len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
