# -*- coding: utf-8 -*-
"""Positive/negative checks for the four dev-driven general rules."""
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
for p in (ROOT / "libs", ROOT / "core"):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions

RULES = {r["id"]: r for r in json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]}
PASS, FAIL = [], []

def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""

def run(label, rid, reactants, target, should_hit):
    rx = rdChemReactions.ReactionFromSmarts(RULES[rid]["smarts"])
    hit = False
    for order in (reactants, list(reversed(reactants))):
        ms = [Chem.MolFromSmiles(s) for s in order]
        if any(m is None for m in ms):
            FAIL.append((label, "bad smiles")); return
        if len(ms) != rx.GetNumReactantTemplates():
            continue
        try:
            got = rx.RunReactants(tuple(ms))
        except Exception as ex:
            FAIL.append((label, "err %s" % ex)); return
        for ps in got:
            if any(x and key(Chem.MolToSmiles(x)) == key(target) for x in ps):
                hit = True
    if hit == should_hit:
        PASS.append(label)
    else:
        FAIL.append((label, "hit=%s want=%s" % (hit, should_hit)))

def main():
    run("boc std", "deprotection_boc_amine_001", ["CNC(=O)OC(C)(C)C"], "CN", True)
    run("boc neg", "deprotection_boc_amine_001", ["CNC(=O)C"], "CN", False)
    run("cbz std", "deprotection_cbz_amine_001", ["CNC(=O)OCc1ccccc1"], "CN", True)
    run("cbz neg", "deprotection_cbz_amine_001", ["CC(C)(C)OC(=O)NC"], "CN", False)
    run("sulfonyl std", "sulfonylation_amine_001", ["CN", "CS(=O)(=O)Cl"], "CS(=O)(=O)NC", True)
    run("sulfonyl neg", "sulfonylation_amine_001", ["CN"], "CS(=O)(=O)NC", False)
    run("urea std", "addition_isocyanate_amine_urea_001", ["CN", "O=C=Nc1ccccc1"], "CNC(=O)Nc1ccccc1", True)
    run("urea neg", "addition_isocyanate_amine_urea_001", ["CN"], "CNC(=O)Nc1ccccc1", False)
    print("RESULT", len(PASS), "/", len(PASS) + len(FAIL), "PASS")
    for x in FAIL:
        print("FAIL", x)
    if FAIL:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
