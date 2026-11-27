# -*- coding: utf-8 -*-
"""Re-score a paozhi holdout JSON by product presence.

Paper convention: a case counts only if the literature reports a product.
A positive case is a hit when the product structure appears in the predicted
targets (status ``consistent`` or ``product_only``).  ``formula_only`` and
``skeleton_only`` are reported separately and are not structural hits.
Negative controls (expected status ``miss``) are excluded from the denominator.

This script does not rerun the engine and does not modify the input JSON.

Usage:
    python -I tools/score_holdout_presence.py reports/holdout_paozhi_20261126.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

POSITIVE = ("consistent", "formula_only")
STRUCT_HIT = ("consistent", "product_only")


def target_statuses(case: dict) -> list[str]:
    return [str(t.get("status")) for t in (case.get("targets") or [])]


def score(case: dict) -> dict:
    exp = str((case.get("expected") or {}).get("status"))
    st = target_statuses(case)
    return {
        "tag": case.get("tag") or case.get("id"),
        "expected": exp,
        "actual": case.get("actual_status"),
        "positive": exp in POSITIVE,
        "structure_hit": any(s in STRUCT_HIT for s in st),
        "formula_hit": any(s == "formula_only" for s in st),
        "target_statuses": st,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -I tools/score_holdout_presence.py <holdout.json>")
        return 2
    src = Path(sys.argv[1]).resolve()
    d = json.loads(src.read_text(encoding="utf-8"))
    rows = [score(c) for c in d.get("cases") or []]
    pos = [r for r in rows if r["positive"]]
    neg = [r for r in rows if not r["positive"]]
    struct = [r for r in pos if r["structure_hit"]]
    formula = [r for r in pos if (not r["structure_hit"]) and r["formula_hit"]]
    neg_hit = [r for r in neg if r["structure_hit"]]

    print("cases            %d" % len(rows))
    print("positive cases   %d" % len(pos))
    print("structure hits   %d/%d = %.1f%%" % (len(struct), len(pos),
                                               100.0 * len(struct) / max(1, len(pos))))
    print("formula-only     %d (upper bound %d/%d = %.1f%%)"
          % (len(formula), len(struct) + len(formula), len(pos),
             100.0 * (len(struct) + len(formula)) / max(1, len(pos))))
    print("positive misses  %d" % (len(pos) - len(struct) - len(formula)))
    print("negative controls %d; product appeared in %d" % (len(neg), len(neg_hit)))
    for r in pos:
        if not r["structure_hit"]:
            print("  non-hit: %-42s expected=%s actual=%s %s"
                  % (r["tag"], r["expected"], r["actual"], r["target_statuses"]))
    out = {
        "source": src.name,
        "convention": "positive cases only; structure hit = consistent/product_only",
        "n_cases": len(rows),
        "n_positive": len(pos),
        "n_structure_hits": len(struct),
        "n_formula_only": len(formula),
        "n_positive_misses": len(pos) - len(struct) - len(formula),
        "n_negative_controls": len(neg),
        "n_negative_with_product": len(neg_hit),
        "cases": rows,
    }
    dst = src.with_name(src.stem + "_presence.json")
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
