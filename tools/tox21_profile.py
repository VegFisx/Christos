# -*- coding: utf-8 -*-
"""Tox21/ToxCast pathway endpoints for two formulas.

NR-* are nuclear-receptor assays, SR-* are stress-response assays.  Both come
from the Tox21/ToxCast panels and are already present in the ADMET cache.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402
RDLogger.DisableLog("rdApp.*")

ADMET = "file:D:/TCMAI/data/admet_cache.db?mode=ro"
ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper")

FORMULAS = [
    ("四君子汤", ROOT / "neoformed_sijunzi_v5_20261024.csv"),
    ("四逆汤", ROOT / "neoformed_sinitang_20261027.csv"),
]

ENDPOINTS = ["NR-AR", "NR-AR-LBD", "NR-AhR", "NR-Aromatase",
             "NR-ER", "NR-ER-LBD", "NR-PPAR-gamma",
             "SR-ARE", "SR-ATAD5", "SR-HSE", "SR-MMP", "SR-p53"]


def key(smi):
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return ""


def collect(path, cur):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    data = {}
    for r in rows:
        k = key(r.get("product_smiles", ""))
        if not k:
            continue
        cur.execute("SELECT data FROM admet WHERE inchikey=?", (k,))
        got = cur.fetchone()
        if got:
            data[k] = json.loads(got[0])
    return len(rows), data


def main() -> int:
    cur = sqlite3.connect(ADMET, uri=True).cursor()
    results = {}
    for name, path in FORMULAS:
        if not path.exists():
            continue
        n, data = collect(path, cur)
        results[name] = (n, data)

    print("%-16s %10s %10s" % ("Tox21 端点", "四君子汤", "四逆汤"))
    print("-" * 40)
    for ep in ENDPOINTS:
        line = "%-16s" % ep
        for name, _ in FORMULAS:
            n, data = results.get(name, (0, {}))
            pk = ep + "_drugbank_approved_percentile"
            vals = [d[pk] for d in data.values()
                    if isinstance(d.get(pk), (int, float))]
            high = sum(1 for v in vals if v >= 90.0)
            line += " %5d/%-4d" % (high, len(vals))
        print(line)

    print()
    for name, (n, data) in results.items():
        print("%s：产物 %d，有 Tox21 数据 %d" % (name, n, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
