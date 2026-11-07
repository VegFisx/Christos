# -*- coding: utf-8 -*-
"""Audit the herb-name resolution cascade against a fixed input set.

Each case carries the outcome the resolver is expected to produce.  The script
reports, per expectation group, how often the cascade returned nothing, one
candidate, or several, and which stage answered.

Read-only: the resolver opens tcm.db through a read-only URI.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "sources", STAGE / "core", STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import herb as H  # noqa: E402

# (input, expectation group, note)
CASES = [
    # exact herb names
    ("甘草", "exact", ""),
    ("当归", "exact", ""),
    ("茯苓", "exact", ""),
    ("白术", "exact", ""),
    ("川芎", "exact", ""),
    ("黄芪", "exact", ""),
    ("人参", "exact", ""),
    ("生地黄", "exact", ""),
    ("大黄", "exact", ""),
    ("桂枝", "exact", ""),
    # aliases / synonym table
    ("黄耆", "alias", "curated synonym of 黄芪"),
    ("龙胆草", "alias", "synonym table; several candidates expected"),
    ("国老", "alias", "classical name for 甘草"),
    ("川军", "alias", "colloquial name for 大黄"),
    ("云苓", "alias", "regional name for 茯苓"),
    # processed forms
    ("炙甘草", "processed", ""),
    ("炒白术", "processed", ""),
    ("姜半夏", "processed", ""),
    ("熟地黄", "processed", ""),
    ("酒大黄", "processed", ""),
    # Latin binomials
    ("Glycyrrhiza uralensis", "latin", ""),
    ("Angelica sinensis", "latin", ""),
    ("Poria cocos", "latin", ""),
    # strings that should not resolve
    ("阿巴阿巴", "negative", "not a herb name"),
    ("zzzz", "negative", "not a herb name"),
    ("测试药名", "negative", "not a herb name"),
    ("甘", "negative", "single character, ambiguous"),
]


def main() -> int:
    conn = H._connect(H.DEFAULT_DB)
    cur = conn.cursor()

    rows = []
    for name, group, note in CASES:
        hits = H._resolve_herb_ids(cur, name)
        stages = sorted({h[2] for h in hits})
        rows.append({
            "input": name,
            "group": group,
            "note": note,
            "n_candidates": len(hits),
            "stages": stages,
            "candidates": [h[1] for h in hits][:8],
        })
    conn.close()

    summary = {}
    for group in ("exact", "alias", "processed", "latin", "negative"):
        sub = [r for r in rows if r["group"] == group]
        n = len(sub)
        resolved = [r for r in sub if r["n_candidates"] > 0]
        ambiguous = [r for r in resolved if r["n_candidates"] > 1]
        stage_counts = Counter(s for r in sub for s in r["stages"])
        summary[group] = {
            "n": n,
            "resolved": len(resolved),
            "unresolved": n - len(resolved),
            "ambiguous": len(ambiguous),
            "stages": dict(stage_counts),
        }

    out = STAGE / "reports" / "paper" / "herb_resolution_audit_20261022.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"cases": rows, "summary": summary},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    for group, s in summary.items():
        print("%-10s n=%2d resolved=%2d unresolved=%2d ambiguous=%2d  %s"
              % (group, s["n"], s["resolved"], s["unresolved"],
                 s["ambiguous"], s["stages"]))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
