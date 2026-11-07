# -*- coding: utf-8 -*-
"""Measure how complete the provenance fields are on a real ledger.

The paper claims that every candidate carries its source compound, herb or
species, reaction rule, round, condition marker, direction marker and evidence
string.  This script checks that claim against an actual run instead of
asserting it.

Usage:
    python tools/audit_provenance_completeness.py <ledger.csv> [...]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Field groups as promised in the manuscript.  A group counts as present when
# at least one of its columns carries a non-empty value.
GROUPS = {
    "product": ["product_smiles"],
    "source_compound": ["source_smiles", "source_name"],
    "source_organism": ["source_herb"],
    "reaction_rule": ["rule_name"],
    "round": ["round"],
    "condition_marker": ["activation", "cond_model"],
    "direction_marker": ["direction", "direction_cn"],
    "evidence_string": ["activation_why", "direction_reason", "direction_source"],
    "template_support": ["template_support"],
    # Checked on its own because a condition marker of "1.0" paired with the
    # text "no ORD condition data, admitted" is a marker without evidence.
    "condition_rationale": ["activation_why"],
}

EMPTY = {"", "na", "n/a", "none", "null", "-", "nan"}

# Values that occupy a field but say "nothing was found".  They count as
# structurally present and substantively absent, and the two must be reported
# separately.
PLACEHOLDER_MARKERS = (
    "无 ord 条件数据",
    "无证据",
    "no evidence",
    "no ord condition data",
)


def is_placeholder(value: str) -> bool:
    v = value.strip().lower()
    return any(m in v for m in PLACEHOLDER_MARKERS)


def substantive_value(row: dict, cols: list[str]) -> bool:
    """True when at least one column carries a value that is not a placeholder."""
    for c in cols:
        v = (row.get(c) or "").strip()
        if not v or v.lower() in EMPTY:
            continue
        if is_placeholder(v):
            continue
        return True
    return False


def has_value(row: dict, cols: list[str]) -> bool:
    for c in cols:
        v = (row.get(c) or "").strip()
        if v and v.lower() not in EMPTY:
            return True
    return False


def audit(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    n = len(rows)
    per_group = {}
    for name, cols in GROUPS.items():
        hits = sum(1 for r in rows if has_value(r, cols))
        per_group[name] = {
            "columns": cols,
            "present": hits,
            "total": n,
            "rate": round(hits / n, 4) if n else 0.0,
        }

    full = sum(
        1 for r in rows
        if all(has_value(r, cols) for cols in GROUPS.values())
    )
    substantive = {
        name: sum(1 for r in rows if substantive_value(r, cols))
        for name, cols in GROUPS.items()
    }
    return {
        "file": path.name,
        "rows": n,
        "per_group": per_group,
        "substantive": {
            k: {"present": v,
                "rate": round(v / n, 4) if n else 0.0}
            for k, v in substantive.items()
        },
        "fully_complete": full,
        "fully_complete_rate": round(full / n, 4) if n else 0.0,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    reports = []
    for arg in argv[1:]:
        p = Path(arg)
        if not p.is_file():
            print("missing: %s" % p)
            return 2
        reports.append(audit(p))

    out = Path(argv[1]).parent / "provenance_completeness.json"
    out.write_text(
        json.dumps(reports, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    for r in reports:
        print("== %s  rows=%d  fully_complete=%.2f%%"
              % (r["file"], r["rows"], r["fully_complete_rate"] * 100))
        for name, g in r["per_group"].items():
            s = r["substantive"][name]
            print("   %-18s fields %6.2f%%  substantive %6.2f%%  (%d/%d)"
                  % (name, g["rate"] * 100, s["rate"] * 100,
                     s["present"], g["total"]))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
