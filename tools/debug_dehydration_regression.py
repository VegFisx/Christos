# -*- coding: utf-8 -*-
"""查脱水的回归：2-丁醇的 2-丁烯产物为什么不见了。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import (Compound, load_engine, _atom_counts_of_smiles,
                    _formula_atoms, _counts_differ)
from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
import templates as T

eng, rules, profs = load_engine()
r = next(x for x in rules if x["id"] == "elimination_dehydration_001")
print("SMARTS:", r["smarts"])
print("co_reagents:", r.get("co_reagents"), "  byproducts:", r.get("byproducts"))
print("limit:", r.get("max_products_per_molecule"))

SUB = "CCC(C)O"
print("\n底物 2-丁醇:", SUB)
print("底物原子:", _atom_counts_of_smiles(SUB))

rxn = rdchiralReaction(r["smarts"])
outs = rdchiralRun(rxn, rdchiralReactants(SUB)) or []
print(f"\nrdchiral 原始产物组: {len(outs)}")
for i, o in enumerate(outs[:6]):
    right = {}
    for formula, n in (r.get("byproducts") or {}).items():
        for el, c in _formula_atoms(formula).items():
            right[el] = right.get(el, 0.0) + c * float(n)
    for part in (p for p in o.split(".") if p):
        for el, c in _atom_counts_of_smiles(part).items():
            right[el] = right.get(el, 0.0) + c
    left = _atom_counts_of_smiles(SUB)
    for formula, n in (r.get("co_reagents") or {}).items():
        for el, c in _formula_atoms(formula).items():
            left[el] = left.get(el, 0.0) + c * float(n)
    differ = _counts_differ(left, right)
    print(f"  [{i}] {o:<22} 左{left} 右{right} {'★配不平，会被丢★' if differ else '配平'}")

print("\n引擎实际产出:")
cond = T.get_template("煎煮")
ps = eng.apply_rule(r, Compound(smiles=SUB, name="2-丁醇", herb="t"), 0.6, 1, cond)
for p in ps:
    print(f"  {p.smiles:<16} {p.formula}")
print("被守卫拦下:", getattr(eng, "balance_dropped", 0))
