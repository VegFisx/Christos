# -*- coding: utf-8 -*-
"""Calibrate the per-herb component limit: products and time at each stop.

The UI used to offer 6 / 12 / 24 with only the 12 point actually measured.
This runs the same herb at several limits so the tiers rest on data.

Usage:
    python tools/calibrate_herb_limit.py [--herb 甘草]
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

LIMITS = [3, 6, 12, 24, 48]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    args = ap.parse_args()

    rows = []
    for lim in LIMITS:
        cs = H.compounds_of_herb(args.herb, limit=lim)
        seeds = [(c.name, c.smiles, "tcm.db:%s" % (c.herb or args.herb))
                 for c in cs if c.smiles]
        n = len(seeds)
        if n < 2:
            print("%2d 个成分：底物不足" % lim)
            continue
        pairs = n * (n - 1) // 2
        t0 = time.time()
        spec = qb.RunSpec(
            seeds=seeds, cond_name="煎煮", rounds=1,
            max_pairs=4000, max_products_per_pair=8,
            use_curated_templates=True, strict_redox_gate=True,
        )
        inv = qb.build_inventory(spec, score=False, use_cache=False)
        sec = time.time() - t0
        rows.append({"limit": lim, "substrates": n, "pairs": pairs,
                     "products": len(inv.paths), "seconds": round(sec, 1)})
        print("%2d 个成分（%4d 对）-> %6d 产物，%6.1f 秒"
              % (lim, pairs, len(inv.paths), sec), flush=True)

    out = STAGE / "reports" / "paper" / "herb_limit_calibration_20261025.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
