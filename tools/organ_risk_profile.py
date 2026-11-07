# -*- coding: utf-8 -*-
"""Compare two formulas across organ-level ADMET endpoints.

This is a compound-level risk profile, not an adverse-reaction prediction:
no dose, no individual variation, no processing method enters the calculation.
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

ENDPOINTS = [
    ("急性毒性", "LD50_Zhu"),
    ("肝损伤", "DILI"),
    ("心脏 hERG", "hERG"),
    ("皮肤反应", "Skin_Reaction"),
    ("临床毒性", "ClinTox"),
    ("致癌性", "Carcinogens_Lagunin"),
]


def key(smi):
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return ""


def profile(path, cur):
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
    out = {"products": len(rows), "with_admet": len(data)}
    for label, ep in ENDPOINTS:
        pk = ep + "_drugbank_approved_percentile"
        vals = [d[pk] for d in data.values()
                if isinstance(d.get(pk), (int, float))]
        high = sum(1 for v in vals if v >= 90.0)
        out[label] = {"n": len(vals), "high": high,
                      "rate": round(100.0 * high / len(vals), 1) if vals else 0.0}
    return out


def main() -> int:
    cur = sqlite3.connect(ADMET, uri=True).cursor()
    results = {}
    for name, path in FORMULAS:
        if not path.exists():
            print("缺文件：%s" % path)
            continue
        results[name] = profile(path, cur)

    print("%-12s %8s %8s" % ("端点", "四君子汤", "四逆汤"))
    print("-" * 34)
    a = results.get("四君子汤") or {}
    b = results.get("四逆汤") or {}
    for label, _ep in ENDPOINTS:
        pa = a.get(label) or {}
        pb = b.get(label) or {}
        print("%-12s %8s %8s"
              % (label,
                 "%d/%d" % (pa.get("high", 0), pa.get("n", 0)),
                 "%d/%d" % (pb.get("high", 0), pb.get("n", 0))))
    print("\n产物数：四君子汤 %d（有 ADMET %d）· 四逆汤 %d（有 ADMET %d）"
          % (a.get("products", 0), a.get("with_admet", 0),
             b.get("products", 0), b.get("with_admet", 0)))

    out = ROOT / "organ_risk_profile_20261027.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
