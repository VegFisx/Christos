# -*- coding: utf-8 -*-
"""Deeper subclass classification of dev misses by formed-bond environment.

Element-level C-N / C-C classes are too coarse.  For each formed bond we look at
the product atoms: carbonyl vs sulfonyl vs aromatic; biaryl vs alkyl-aryl;
ring closure; etc.  Dev only; blind sets are not used.
"""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT / "tools"):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
import mapped_chem as mc
from rxnmapper import RXNMapper

CASES = json.loads((ROOT / "data" / "dev_general_organic_20261124.json").read_text(encoding="utf-8"))["cases"]
RES = json.loads((ROOT / "reports" / "general_organic_full_lf_dev_20261124.json").read_text(encoding="utf-8"))["rows"]
MISS = {r["id"] for r in RES if not r.get("hit")}
rows = [c for c in CASES if c["id"] in MISS]
mapper = RXNMapper()

def is_carbonyl(a):
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2:
            return True
    return False

def is_sulfonyl(a):
    for b in a.GetBonds():
        o = b.GetOtherAtom(a)
        if o.GetSymbol() == "O" and b.GetBondTypeAsDouble() == 2:
            return True
    return False

def c_n_class(c_atom, n_atom, bond):
    if c_atom.GetIsAromatic() and not n_atom.GetIsAromatic():
        return "aryl_amine"
    if is_carbonyl(c_atom):
        return "amide_urea_carbamate"
    if c_atom.GetIsAromatic():
        return "aryl_amine"
    return "alkyl_amine"

def c_c_class(a, b, bond):
    aa, ab = a.GetIsAromatic(), b.GetIsAromatic()
    if aa and ab:
        return "biaryl"
    if aa or ab:
        return "aryl_alkyl"
    if a.GetHybridization() == Chem.HybridizationType.SP or b.GetHybridization() == Chem.HybridizationType.SP:
        return "alkyne"
    if bond.IsInRing():
        return "ring_closure"
    if is_carbonyl(a) or is_carbonyl(b):
        return "carbonyl_alpha"
    return "alkyl_alkyl"

def c_o_class(c, o, bond):
    if is_carbonyl(c):
        return "ester_carbonate"
    if c.GetIsAromatic():
        return "aryl_ether"
    if bond.IsInRing():
        return "ring_O"
    return "ether"

CLASSES = Counter()
EX = defaultdict(list)
fail = []
for c in rows:
    rxn = ".".join(c["reactants"]) + ">>" + c["product"]
    try:
        mr = mapper.get_attention_guided_atom_maps([rxn])[0].get("mapped_rxn") or ""
        lhs, rhs = mr.split(">>", 1)
        prod = mc.parse_mapped(rhs, context=c["id"])
        if prod is None:
            raise ValueError("no product")
        raws, _ = mc.contributing_components(lhs, mc.map_nums(prod))
        left = mc.bonds_over_maps_all(raws)
        formed, _broken = mc.formed_broken(prod, left)
        bymap = {a.GetAtomMapNum(): a for a in prod.GetAtoms() if a.GetAtomMapNum()}
        tags = set()
        for x, y in formed:
            a, b = bymap.get(x), bymap.get(y)
            if a is None or b is None:
                continue
            bond = prod.GetBondBetweenAtoms(a.GetIdx(), b.GetIdx())
            if bond is None:
                continue
            sa, sb = a.GetSymbol(), b.GetSymbol()
            if {sa, sb} == {"C", "N"}:
                cc, nn = (a, b) if sa == "C" else (b, a)
                tags.add("C-N/" + c_n_class(cc, nn, bond))
            elif {sa, sb} == {"C", "C"}:
                tags.add("C-C/" + c_c_class(a, b, bond))
            elif {sa, sb} == {"C", "O"}:
                cc, oo = (a, b) if sa == "C" else (b, a)
                tags.add("C-O/" + c_o_class(cc, oo, bond))
            elif {sa, sb} == {"C", "S"}:
                tags.add("C-S/other")
            elif {sa, sb} == {"C", "Br"}:
                tags.add("C-Br")
            elif {sa, sb} == {"C", "Cl"}:
                tags.add("C-Cl")
        # protecting-group context
        for r in c["reactants"]:
            if "OC(=O)C(C)(C)C" in r or "OC(C)(C)C" in r:
                tags.add("ctx/Boc")
            if "OCc1ccccc1" in r:
                tags.add("ctx/Cbz")
        key = "|".join(sorted(tags)) or "(no mapped formed bond)"
        CLASSES[key] += 1
        if len(EX[key]) < 2:
            EX[key].append(c)
    except Exception as ex:
        fail.append((c["id"], str(ex)))

print("misses", len(rows), "failed", len(fail))
for k, n in CLASSES.most_common(40):
    print("\n", n, k)
    for c in EX[k][:1]:
        print("  ", c["id"], "R", " | ".join(c["reactants"])[:180])
        print("      P", c["product"][:180])

out = {"n_misses": len(rows), "failed": fail,
       "classes": [{"signature": k, "n": n, "examples": EX[k]} for k, n in CLASSES.most_common()]}
(ROOT / "reports" / "dev_reaction_subclasses_20261124.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwritten reports/dev_reaction_subclasses_20261124.json")
