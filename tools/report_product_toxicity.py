# -*- coding: utf-8 -*-
"""Join predicted products against the ADMET cache and surface risk flags."""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402
RDLogger.DisableLog("rdApp.*")

CSV_IN = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
              r"\neoformed_sinitang_20261027.csv")
ADMET = "file:D:/TCMAI/data/admet_cache.db?mode=ro"

FLAGS = ["LD50_Zhu", "hERG", "DILI", "AMES", "ClinTox", "Carcinogens_Lagunin"]


def key(smi):
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return ""


def main() -> int:
    rows = list(csv.DictReader(CSV_IN.open(encoding="utf-8-sig")))
    cur = sqlite3.connect(ADMET, uri=True).cursor()

    joined = []
    for r in rows:
        k = key(r.get("product_smiles", ""))
        if not k:
            continue
        cur.execute("SELECT data FROM admet WHERE inchikey=?", (k,))
        got = cur.fetchone()
        if not got:
            continue
        d = json.loads(got[0])
        joined.append((r, d))

    print("命中 ADMET 的产物 %d 条\n" % len(joined))

    # 每个端点：高风险 = 百分位 > 0.9
    for f in FLAGS:
        pkey = f + "_drugbank_approved_percentile"
        vals = [(r, d) for r, d in joined if isinstance(d.get(pkey), (int, float))]
        if not vals:
            continue
        high = [(r, d) for r, d in vals if d[pkey] >= 90.0]
        print("%-22s 有值 %3d 条，高风险(≥90 百分位) %2d 条" % (f, len(vals), len(high)))
        for r, d in high[:3]:
            print("    %-30s 百分位 %.2f  %s"
                  % (r.get("rule_name", "")[:30], d[pkey],
                     (r.get("product_smiles") or "")[:44]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
