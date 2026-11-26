# -*- coding: utf-8 -*-
"""Report candidate burden from run_general_holdout result JSONs.

This is deliberately NOT called precision: the current engine has no calibrated
false-positive/feasibility model.  What we can measure is how many candidates a
case emits, how often the target is among them, and how the exact hit rate falls
as the candidate count grows.  That is enough to expose the practical review
cost without pretending it is selectivity.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "295": ROOT / "reports" / "general_organic_295_20261123.json",
    "blind1": ROOT / "reports" / "general_organic_blind_20261124.json",
    "blind2": ROOT / "reports" / "general_organic_blind2_20261124.json",
}
OUT = ROOT / "reports" / "candidate_burden_20261124.json"

def pct(x, n):
    return round(100.0 * x / n, 2) if n else 0.0

def summarize(rows):
    ns = [int(r.get("n_products") or 0) for r in rows]
    if not ns:
        return {}
    s = sorted(ns)
    def q(p):
        return s[min(len(s) - 1, int(p * (len(s) - 1)))]
    return {
        "n": len(rows),
        "mean_products": round(statistics.mean(ns), 2),
        "median_products": statistics.median(ns),
        "p90_products": q(0.90),
        "max_products": max(ns),
        "cases_gt_16": sum(x > 16 for x in ns),
        "cases_gt_32": sum(x > 32 for x in ns),
        "cases_gt_64": sum(x > 64 for x in ns),
        "skeleton_hits": sum(bool(r.get("skeleton")) for r in rows),
        "exact_hits": sum(bool(r.get("exact")) for r in rows),
    }

def main() -> int:
    out = {}
    for label, path in FILES.items():
        if not path.exists():
            print("skip missing", label, path)
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        out[label] = {}
        for cfg, rows in d.get("results", {}).items():
            s = summarize(rows)
            out[label][cfg] = s
            print(label, cfg, json.dumps(s, ensure_ascii=False))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", OUT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
