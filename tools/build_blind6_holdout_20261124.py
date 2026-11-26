# -*- coding: utf-8 -*-
"""Freeze blind6 from MIT, disjoint from all prior sets (295/blind1-5/dev)."""
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
OUT = ROOT / "data" / "holdout_general_organic_blind6_20261124.json"
SEED = 20261206
N = 300


def canon(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""


def load(name):
    p = ROOT / "data" / name
    return json.loads(p.read_text(encoding="utf-8")).get("cases", [])


sets = [
    "holdout_general_organic_295_20261123.json",
    "holdout_general_organic_blind_20261124.json",
    "holdout_general_organic_blind2_20261124.json",
    "dev_general_organic_20261124.json",
    "holdout_general_organic_blind3_20261124.json",
    "holdout_general_organic_blind4_20261124.json",
    "holdout_general_organic_blind5_20261124.json",
]
prev = []
for n in sets:
    prev.extend(load(n))
hold_prod = {canon(c["product"]) for c in prev}
hold_sets = {tuple(sorted(canon(x) for x in c["reactants"])) for c in prev}

rng = random.Random(SEED)
res, seen = [], set()
n_valid = 0
with SRC.open(encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        rxn = row.get("reactions") or ""
        if rxn.count(">") < 2:
            continue
        lhs, _a, rhs = rxn.split(">", 2)
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
        if pk in hold_prod or rk in hold_sets:
            continue
        key = (rk, pk)
        if key in seen:
            continue
        seen.add(key)
        n_valid += 1
        item = {"id": "blind6_%04d" % n_valid, "class": "blind6",
                "n_reactants": 2, "reactants": rs, "product": ps[0]}
        if len(res) < N:
            res.append(item)
        else:
            j = rng.randrange(n_valid)
            if j < N:
                res[j] = item

for i, item in enumerate(res, 1):
    item["id"] = "blind6_%04d" % i

out = {
    "schema": "blind_general_organic_holdout_v1",
    "generated_at": "2026-11-24",
    "source": "MIT USPTO (fresh split 6)",
    "seed": SEED,
    "note": ("Frozen after round-215 (no rule changes since the round-213 family "
             "rules); disjoint from 295/blind1-5/dev by exact reactant-set and "
             "product match."),
    "n": len(res),
    "cases": res,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("valid", n_valid, "sampled", len(res), "->", OUT)
