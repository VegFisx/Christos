# -*- coding: utf-8 -*-
"""Freeze a second blind holdout from USPTO-50k train-like rows.

Excludes exact matches with the 295 evaluation set and the first blind set.
This is a fresh test; do not inspect individual misses until after the
independent engine/template change is frozen.
"""
from __future__ import annotations
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

SRC = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = ROOT / "data" / "holdout_general_organic_blind2_20261124.json"
SEED = 20261125
N = 300

def canon(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""

def old_cases(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return d.get("cases", [])

old = old_cases(ROOT / "data" / "holdout_general_organic_295_20261123.json")
blind1 = old_cases(ROOT / "data" / "holdout_general_organic_blind_20261124.json")
hold_prod = {canon(c["product"]) for c in old + blind1}
hold_sets = {tuple(sorted(canon(x) for x in c["reactants"])) for c in old + blind1}
hold_ids = {c["id"].replace("uspto50k_test_", "") for c in old}
blind1_ids = {c["id"] for c in blind1}

rng = random.Random(SEED)
reservoir = []
seen = set()
n_valid = 0
with SRC.open(encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d.get("id") in hold_ids:
            continue
        rs = d.get("reactants") or []
        prod = d.get("product") or ""
        if len(rs) != 2 or not prod:
            continue
        rm = [Chem.MolFromSmiles(x) for x in rs]
        pm = Chem.MolFromSmiles(prod)
        if any(m is None for m in rm) or pm is None:
            continue
        if any(len(Chem.GetMolFrags(m)) != 1 for m in rm + [pm]):
            continue
        if not (60 <= sum(Descriptors.MolWt(m) for m in rm) <= 900):
            continue
        if not (100 <= Descriptors.MolWt(pm) <= 650):
            continue
        rk = tuple(sorted(canon(x) for x in rs))
        pk = canon(prod)
        if pk in hold_prod or rk in hold_sets:
            continue
        key = (rk, pk)
        if key in seen:
            continue
        seen.add(key)
        n_valid += 1
        item = {"id": "blind2_%04d" % n_valid, "class": "blind2",
                "n_reactants": 2, "reactants": rs, "product": prod}
        if len(reservoir) < N:
            reservoir.append(item)
        else:
            j = rng.randrange(n_valid)
            if j < N:
                reservoir[j] = item

for i, item in enumerate(reservoir, 1):
    item["id"] = "blind2_%04d" % i

out = {
    "schema": "blind_general_organic_holdout_v1",
    "generated_at": "2026-11-24",
    "source": "USPTO-50k canon (reports/paper/data/uspto50k_canon.jsonl)",
    "seed": SEED,
    "note": "Frozen before template-limit evaluation; exact 295/blind1 matches excluded.",
    "n": len(reservoir),
    "cases": reservoir,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("valid", n_valid, "sampled", len(reservoir), "->", OUT)
