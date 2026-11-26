# -*- coding: utf-8 -*-
"""Regenerate reports/rules_unvalidated_backlog_<date>.md from rules.json.

Read-only view of the provenance ledger: which active rules are still
`unvalidated`.  It never edits rules.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = d["rules"]
    active = [r for r in rules if str(r.get("status") or "active") == "active"]
    unv = [r for r in active if str(r.get("provenance") or "unvalidated") == "unvalidated"]
    cited = [r for r in active if str(r.get("provenance") or "unvalidated") == "cited"]
    by_cat = defaultdict(list)
    for r in unv:
        by_cat[str(r.get("category") or "other")].append(r["id"])

    out = Path(args.out) if args.out else (
        ROOT / "reports" / ("rules_unvalidated_backlog_%s.md"
                            % _dt.date.today().strftime("%Y%m%d")))

    lines = ["# Unvalidated rule backlog (%s)" % _dt.date.today().isoformat(), "",
             "Rules: %d total / %d active / %d cited / %d active unvalidated"
             % (len(rules), len(active), len(cited), len(unv)), "",
             "| category | n | rules |", "|---|---:|---|"]
    for cat in sorted(by_cat):
        ids = sorted(by_cat[cat])
        lines.append("| %s | %d | %s |" % (cat, len(ids), ", ".join(ids)))
    lines += ["",
              "These rules are exploratory only; the file-level default load is "
              "%d cited rules. Promote only after an independent literature or "
              "reaction-data check. Do not modify existing rules in place."
              % len(cited), ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    print("active=%d cited=%d unvalidated=%d" % (len(active), len(cited), len(unv)))
    print("written", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
