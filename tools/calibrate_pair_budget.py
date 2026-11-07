# -*- coding: utf-8 -*-
"""Calibrate the pair budget: how many products and how much time for each cap.

Runs the same substrate set at several ``max_pairs`` values and reports the
candidate count and wall time.  The point is to find where the curve flattens,
so the default has a measurement behind it rather than a guess.

Usage:
    python tools/calibrate_pair_budget.py [--limit 200] [--herb 甘草]
"""
from __future__ import annotations

import argparse
import json
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

import herb as H          # noqa: E402
import query_base as qb   # noqa: E402

BUDGETS = [500, 1000, 2000, 4000, 8000]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    cs = H.compounds_of_herb(args.herb, limit=args.limit)
    seeds = [(c.name, c.smiles, "tcm.db:%s" % (c.herb or args.herb))
             for c in cs if c.smiles]
    n = len(seeds)
    total_pairs = n * (n - 1) // 2
    print("%s：%d 个成分，理论上限 %d 对" % (args.herb, n, total_pairs))

    rows = []
    for budget in BUDGETS:
        t0 = time.time()
        spec = qb.RunSpec(
            seeds=seeds,
            cond_name="煎煮",
            rounds=1,
            max_pairs=budget,
            max_products_per_pair=8,
            use_curated_templates=True,
            strict_redox_gate=True,
        )
        inv = qb.build_inventory(spec, score=False, use_cache=False)
        sec = time.time() - t0
        rows.append({
            "max_pairs": budget,
            "effective_pairs": min(budget, total_pairs),
            "products": len(inv.paths),
            "seconds": round(sec, 1),
        })
        print("预算 %5d（实际 %5d 对）-> %6d 产物，%6.1f 秒"
              % (budget, min(budget, total_pairs), len(inv.paths), sec))

    out = STAGE / "reports" / "paper" / "pair_budget_calibration_20261025.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
