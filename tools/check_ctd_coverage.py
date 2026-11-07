# -*- coding: utf-8 -*-
"""How many predicted products have a CTD chemical-disease association?

CTD keys on MeSH chemical names, so the join runs through the herb table's
English compound names.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402
RDLogger.DisableLog("rdApp.*")

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
CTD = ROOT / "data" / "CTD_chemicals_diseases.csv"
FORMULAS = [
    ("四君子汤", ROOT / "reports" / "paper" / "neoformed_sijunzi_v5_20261024.csv"),
    ("四逆汤", ROOT / "reports" / "paper" / "neoformed_sinitang_20261027.csv"),
]


def key(smi):
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return ""


def main() -> int:
    # 1) 产物 -> InChIKey -> 英文名
    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    cur.execute("SELECT inchi_key, name_en FROM compounds "
                "WHERE inchi_key IS NOT NULL AND TRIM(inchi_key)<>''")
    ik2name = {r[0]: (r[1] or "").strip() for r in cur.fetchall()}
    print("tcm.db 有英文名的化合物 %d" % len(ik2name))

    wanted = {}
    for label, path in FORMULAS:
        if not path.exists():
            continue
        names = set()
        rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
        for r in rows:
            k = key(r.get("product_smiles", ""))
            nm = ik2name.get(k)
            if nm:
                names.add(nm.lower())
        wanted[label] = names
        print("%s：产物 %d，能查到英文名 %d 个" % (label, len(rows), len(names)))

    all_names = set().union(*wanted.values()) if wanted else set()
    print("待匹配英文名合计 %d" % len(all_names))

    # 2) 扫 CTD，只保留名字命中的行
    hits = defaultdict(set)
    n_rows = 0
    with CTD.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            n_rows += 1
            if n_rows % 1000000 == 0:
                print("  CTD 已扫 %d 万行" % (n_rows // 10000), flush=True)
            parts = line.rstrip("\n").split(",")
            if len(parts) < 5:
                continue
            nm = parts[0].strip().lower()
            if nm in all_names:
                hits[nm].add(parts[3].strip())

    print("\nCTD 关联行 %d 万" % (n_rows // 10000))
    for label, names in wanted.items():
        got = [n for n in names if n in hits]
        nd = sum(len(hits[n]) for n in got)
        print("%s：命中成分 %d / %d（%.1f%%），涉及疾病 %d 个"
              % (label, len(got), len(names),
                 100.0 * len(got) / max(1, len(names)), nd))
        for n in got[:5]:
            print("    %-40s → %s" % (n[:40], "；".join(sorted(hits[n])[:3])))

    out = ROOT / "reports" / "paper" / "ctd_coverage_20261027.json"
    out.write_text(json.dumps({
        "ctd_rows": n_rows,
        "hits": {k: sorted(v) for k, v in hits.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
