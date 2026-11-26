# -*- coding: utf-8 -*-
"""Build a pre-registered blind general-organic holdout from the MIT USPTO set.

The 295-case USPTO test sample is no longer a clean holdout at the selection
level: rounds 205-207 chose which gaps to work on after seeing its misses.  This
script samples a different 300 reactions from the 479k MIT USPTO set, excluding
every exact reactant-set/product match with the 295 cases.  It is run and frozen
BEFORE any rule is tuned on it.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "libs"))
from rdkit import Chem, RDLogger
from rdkit.Chem import Descriptors

RDLogger.DisableLog("rdApp.*")

SRC = ROOT / "reports" / "paper" / "data" / "uspto_mit" / "USPTO_MIT.csv"
OUT = ROOT / "data" / "holdout_general_organic_blind_20261124.json"
SEED = 20261124
N = 300

CASES295 = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                      .read_text(encoding="utf-8"))["cases"]

def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""

HOLD_PROD = {canon(c["product"]) for c in CASES295}
HOLD_SETS = {tuple(sorted(canon(x) for x in c["reactants"])) for c in CASES295}

rng = random.Random(SEED)
reservoir = []
seen = set()
n_valid = 0
with SRC.open(encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        rxn = row.get("reactions") or ""
        if rxn.count(">") < 2:
            continue
        lhs, _agents, rhs = rxn.split(">", 2)
        rs = [x for x in lhs.split(".") if x]
        ps = [x for x in rhs.split(".") if x]
        if len(rs) != 2 or len(ps) != 1:
            continue
        rm = [Chem.MolFromSmiles(x) for x in rs]
        pm = Chem.MolFromSmiles(ps[0])
        if any(m is None for m in rm) or pm is None:
            continue
        if any(len(Chem.GetMolFrags(m)) != 1 for m in rm + [pm]):
            continue
        if not (60 <= sum(Descriptors.MolWt(m) for m in rm) <= 900):
            continue
        if not (100 <= Descriptors.MolWt(pm) <= 650):
            continue
        rk = tuple(sorted(canon(x) for x in rs))
        pk = canon(ps[0])
        if pk in HOLD_PROD or rk in HOLD_SETS:
            continue
        key = (rk, pk)
        if key in seen:
            continue
        seen.add(key)
        n_valid += 1
        item = {
            "id": "blind_%04d" % n_valid,
            "class": "blind",
            "n_reactants": 2,
            "reactants": rs,
            "product": ps[0],
        }
        if len(reservoir) < N:
            reservoir.append(item)
        else:
            j = rng.randrange(n_valid)
            if j < N:
                reservoir[j] = item

# Keep stable, source-order-independent ids for the sampled rows.
for i, item in enumerate(reservoir, 1):
    item["id"] = "blind_%04d" % i

out = {
    "schema": "blind_general_organic_holdout_v1",
    "generated_at": "2026-11-24",
    "source": "MIT USPTO (reports/paper/data/uspto_mit/USPTO_MIT.csv)",
    "seed": SEED,
    "note": ("Sampled before evaluation; exact 295 reactant/product matches excluded. "
             "No rule was tuned on these cases."),
    "n": len(reservoir),
    "cases": reservoir,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("valid", n_valid, "sampled", len(reservoir), "->", OUT)
