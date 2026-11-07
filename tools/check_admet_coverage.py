# -*- coding: utf-8 -*-
"""How many predicted products have an ADMET entry?

This decides whether the toxicity layer is viable: if the cache does not cover
the products the engine generates, there is nothing to join against.
"""
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
              r"\neoformed_sijunzi_v5_20261024.csv")
ADMET = "file:D:/TCMAI/data/admet_cache.db?mode=ro"


def inchikey(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return ""


def main() -> int:
    rows = list(csv.DictReader(CSV_IN.open(encoding="utf-8-sig")))
    print("产物 %d 条" % len(rows))

    cur = sqlite3.connect(ADMET, uri=True).cursor()
    cur.execute("SELECT inchikey FROM admet")
    have = {r[0] for r in cur.fetchall()}
    print("ADMET 缓存 %d 个 InChIKey" % len(have))

    hit = 0
    miss = []
    by_rule = Counter()
    hit_by_rule = Counter()
    for r in rows:
        k = inchikey(r.get("product_smiles", ""))
        rule = r.get("rule_name", "?")
        by_rule[rule] += 1
        if k and k in have:
            hit += 1
            hit_by_rule[rule] += 1
        elif len(miss) < 5:
            miss.append((rule, r.get("product_smiles", "")[:60]))

    print("\n命中 %d / %d（%.1f%%）" % (hit, len(rows), 100.0 * hit / max(1, len(rows))))
    if miss:
        print("未命中示例：")
        for rule, smi in miss:
            print("   %-32s %s" % (rule, smi))

    print("\n按规则分组的命中率：")
    for rule, n in by_rule.most_common(10):
        print("   %-34s %5d / %5d  (%.1f%%)"
              % (rule, hit_by_rule[rule], n, 100.0 * hit_by_rule[rule] / n))

    out = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
               r"\admet_coverage_20261027.json")
    out.write_text(json.dumps({
        "products": len(rows), "admet_keys": len(have), "hits": hit,
        "by_rule": {k: [hit_by_rule[k], v] for k, v in by_rule.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
