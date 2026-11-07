# -*- coding: utf-8 -*-
"""Check whether Christos predicts a set of literature-documented conversions.

Each case names a substrate and the product reported in the literature.  The
engine runs one substrate through the decoction condition profile and the
script reports whether the expected product appears, in which round, and under
which rule.

This is a qualitative coverage check, not a benchmark.  Five cases cannot
establish accuracy; they establish whether the pipeline can reach the
transformations at all.

Usage:
    python tools/verify_known_conversions.py [--rounds 2] [--cond 煎煮]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs",
           STAGE / "tools", STAGE / "sources", STAGE / "conditions"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

import query_base as qb          # noqa: E402

RDLogger.DisableLog("rdApp.*")

DB = "file:D:/TCMAI/tcm.db?mode=ro"

# (label, substrate name in tcm.db, expected product name in tcm.db)
CASES = [
    ("甘草酸 → 甘草次酸（煎煮水解）",
     "Glycyrrhizic acid", "18beta-glycyrrhetinic acid"),
    ("人参皂苷 Rb1 → Rg3（脱糖）",
     "Ginsenoside rb1", "Ginsenoside rg3"),
    ("乌头碱 → 苯甲酰乌头原碱（脱乙酰）",
     "Aconitine", "Benzoylaconine"),
    ("苯甲酰乌头原碱 → 乌头原碱（脱苯甲酰）",
     "Benzoylaconine", "Aconine"),
    ("芦丁 → 槲皮素（脱芸香糖）",
     "Rutin", "Quercetin"),
]


def canon(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToSmiles(m) if m else ""


def fetch(cur, name):
    cur.execute(
        "SELECT name_en, smiles FROM compounds "
        "WHERE lower(name_en)=lower(?) AND smiles IS NOT NULL LIMIT 1", (name,))
    return cur.fetchone()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--cond", default="煎煮")
    args = ap.parse_args()

    cur = sqlite3.connect(DB, uri=True).cursor()
    rows = []

    for label, sub_name, prod_name in CASES:
        sub = fetch(cur, sub_name)
        prod = fetch(cur, prod_name)
        if not sub or not prod:
            rows.append({"case": label, "status": "missing_in_db",
                         "detail": sub_name if not sub else prod_name})
            print("%-42s MISSING" % label)
            continue

        target = canon(prod[1])
        seed = (sub[0], sub[1], "tcm.db:case")
        t0 = time.time()
        spec = qb.RunSpec(
            seeds=[seed],
            cond_name=args.cond,
            rounds=args.rounds,
            max_pairs=1,
            max_products_per_pair=64,
            use_curated_templates=True,
            strict_redox_gate=True,
        )
        inv = qb.build_inventory(spec, score=False, use_cache=False)

        hit_round = None
        hit_rule = ""
        for p in inv.paths:
            if canon(p.get("product_smiles") or "") == target:
                hit_round = p.get("round")
                hit_rule = p.get("rule_name") or ""
                break

        status = "hit" if hit_round is not None else "miss"
        rows.append({
            "case": label,
            "status": status,
            "round": hit_round,
            "rule": hit_rule,
            "n_products": len(inv.paths),
            "seconds": round(time.time() - t0, 1),
        })
        print("%-42s %-5s round=%s rule=%s products=%d (%.1fs)"
              % (label, status.upper(), hit_round, hit_rule or "-",
                 len(inv.paths), time.time() - t0))

    out = STAGE / "reports" / "paper" / "known_conversions_20261024.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    hit = sum(1 for r in rows if r.get("status") == "hit")
    print("\n命中 %d / %d" % (hit, len(rows)))
    print("结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
