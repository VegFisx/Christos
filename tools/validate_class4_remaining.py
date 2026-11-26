# -*- coding: utf-8 -*-
"""Independent checks for the five class-4 rules added in rounds 205-206.

Conrad-Limpach (alpha-aryl), indazole, Fischer aza-indole, Larock indole and
Hantzsch thiazole.  The templates are derived from standard examples only; the
held-out cases are used here as tests, not as template sources.  Checks:
standard case, held-out case, both reactant orders, product skeleton, and atom
balance.  Negative controls must not hit.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT / "tools", ROOT / "core"):
    sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions, rdMolDescriptors

RULES = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
BY_ID = {r["id"]: r for r in RULES}
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY_CASE = {c["id"]: c for c in CASES}

PASS, FAIL = [], []


def key(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def formula_atoms(mol: Chem.Mol) -> Counter:
    mh = Chem.AddHs(mol)
    return Counter(a.GetSymbol() for a in mh.GetAtoms())


def check_balance(reactants, products) -> bool:
    left = Counter()
    for s in reactants:
        m = Chem.MolFromSmiles(s)
        if m is None:
            return False
        left += formula_atoms(m)
    right = Counter()
    for s in products:
        m = Chem.MolFromSmiles(s)
        if m is None:
            return False
        right += formula_atoms(m)
    return left == right


def run_one(label: str, rule_id: str, reactants, target: str,
            must_hit: bool) -> None:
    rule = BY_ID.get(rule_id)
    if rule is None:
        FAIL.append((label, "rule missing"))
        return
    rx = rdChemReactions.ReactionFromSmarts(rule["smarts"])
    hits, all_products = False, set()
    for order in (reactants, list(reversed(reactants))):
        mols = [Chem.MolFromSmiles(s) for s in order]
        if any(m is None for m in mols):
            FAIL.append((label, "bad reactant SMILES"))
            return
        try:
            got = rx.RunReactants(tuple(mols))
        except Exception as ex:
            FAIL.append((label, "apply error: %s" % ex))
            return
        for ps in got:
            smis = [Chem.MolToSmiles(x) for x in ps if x is not None]
            all_products.update(smis)
            if any(key(s) == key(target) for s in smis):
                hits = True
                if not check_balance(reactants, smis):
                    FAIL.append((label, "hit but atom balance failed: %s" % smis))
                    return
                break
        if hits:
            break
    if hits == must_hit:
        PASS.append((label, "hit" if hits else "no hit"))
    else:
        FAIL.append((label, "expected hit=%s, got %s; products=%s" %
                     (must_hit, hits, sorted(all_products)[:5])))


def run_intra(label: str, rule_id: str, substrate: str, target: str,
              must_hit: bool) -> None:
    """Check a same-molecule (intramolecular) pair rule."""
    from smartreact_engine import _apply_intra_pair
    rule = BY_ID.get(rule_id)
    if rule is None:
        FAIL.append((label, "rule missing"))
        return
    rx = rdChemReactions.ReactionFromSmarts(rule["smarts"])
    mol = Chem.MolFromSmiles(substrate)
    got = _apply_intra_pair(rx, mol,
                            min_path=int(rule.get("intra_min_path") or 8))
    hit = False
    for group in got:
        for frag in group.split("."):
            if frag and key(frag) == key(target):
                hit = True
    if hit == must_hit:
        PASS.append((label, "hit" if hit else "no hit"))
    else:
        FAIL.append((label, "expected hit=%s, got %s; products=%s" %
                     (must_hit, hit, sorted(got)[:4])))


def main() -> None:
    conrad = "cyclization_conrad_limpach_alpha_aryl_001"
    indazole = "cyclization_indazole_001"

    # Standard examples (the template source).
    run_one("conrad std", conrad,
            ["Nc1ccccc1", "CCOC(=O)C(c1ccccc1)C(C)=O"],
            "Cc1[nH]c2ccccc2c(=O)c1-c1ccccc1", True)
    run_one("indazole std", indazole,
            ["O=C(c1ccccc1)c1ccccc1F", "NNc1ccccc1"],
            "c1ccc(-c2nn(-c3ccccc3)c3ccccc23)cc1", True)

    # Held-out cases (not used to derive the templates).
    c1 = BY_CASE["uspto50k_test_US09018229B2"]
    run_one("conrad held-out", conrad, list(c1["reactants"]), c1["product"], True)
    c2 = BY_CASE["uspto50k_test_US20040167127A1"]
    run_one("indazole held-out", indazole, list(c2["reactants"]), c2["product"], True)

    # Negative controls.
    run_one("conrad no alpha-aryl", conrad,
            ["Nc1ccccc1", "CCOC(=O)CC(C)=O"],
            "Cc1[nH]c2ccccc2c(=O)c1", False)
    run_one("indazole no ortho-F", indazole,
            ["O=C(c1ccccc1)c1ccccc1", "NNc1ccccc1"],
            "c1ccc(-c2nn(-c3ccccc3)c3ccccc23)cc1", False)

    # Round-206 additions: independent standard templates for the other three
    # class-4 gaps.
    fischer = "cyclization_fischer_aza_indole_001"
    larock = "cyclization_larock_indole_001"
    hantzsch = "cyclization_hantzsch_thiazole_001"

    run_one("fischer std", fischer,
            ["O=C(Cc1ccccc1)c1ncco1", "NNc1ccccn1"],
            "c1cnc2[nH]c(-c3ncco3)c(-c3ccccc3)c2c1", True)
    run_one("fischer held-out", fischer,
            list(BY_CASE["uspto50k_test_US20050261331A1"]["reactants"]),
            BY_CASE["uspto50k_test_US20050261331A1"]["product"], True)
    run_one("fischer no alpha-aryl ketone", fischer,
            ["CC(=O)c1ccccc1", "NNc1ccccn1"],
            "c1ccc(-c2cc3ncccc3[nH]2)cc1", False)

    run_one("larock std", larock,
            ["C[Si](C)(C)C#CC1CCCCC1", "Nc1ccccc1I"],
            "C[Si](C)(C)c1c(C2CCCCC2)c2ccccc2[nH]1", True)
    run_one("larock held-out", larock,
            list(BY_CASE["uspto50k_test_US20070167447A1"]["reactants"]),
            BY_CASE["uspto50k_test_US20070167447A1"]["product"], True)
    run_one("larock terminal alkyne", larock,
            ["C#Cc1ccccc1", "Nc1ccccc1I"],
            "c1ccc2[nH]c(-c3ccccc3)cc2c1", False)

    run_one("hantzsch std", hantzsch,
            ["O=C1C(Br)CCOc2ccccc21", "NNC(N)=S"],
            "NNc1nc2c(s1)CCOc1ccccc1-2", True)
    run_one("hantzsch held-out", hantzsch,
            list(BY_CASE["uspto50k_test_US20090247567A1"]["reactants"]),
            BY_CASE["uspto50k_test_US20090247567A1"]["product"], True)
    run_one("hantzsch acyclic bromoketone", hantzsch,
            ["O=C(CBr)c1ccccc1", "NNC(N)=S"],
            "NNc1nc(-c2ccccc2)cs1", False)

    # Same-molecule macro-lactam rule (engine intramolecular mode).
    macro = "cyclization_macro_lactam_001"
    run_intra("macro std", macro,
              "CNC(=O)C(C)CC(O)C(Cc1cccc(OCCCCCC(=O)O)c1)NC(=O)C(C)[NH3+]",
              "CNC(=O)C(C)CC(O)C1Cc2cccc(c2)OCCCCCC(=O)NC(C)C(=O)N1", True)
    run_intra("macro held-out", macro,
              BY_CASE["uspto50k_test_US20080070885A1"]["reactants"][0],
              BY_CASE["uspto50k_test_US20080070885A1"]["product"], True)
    run_intra("macro short chain", macro, "NCCCC(=O)O",
              "O=C1CCCN1", False)

    print("=" * 72)
    for label, why in PASS:
        print("PASS", label, "-", why)
    for label, why in FAIL:
        print("FAIL", label, "-", why)
    print("=" * 72)
    print("RESULT %d/%d PASS" % (len(PASS), len(PASS) + len(FAIL)))
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
