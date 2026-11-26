# -*- coding: utf-8 -*-
r"""Promote rules with strong ORD execution evidence to provenance=secondary.

Reads the combined evidence report (build_rule_evidence_report.py) and only
touches the `provenance` field of the rules it promotes.  Dry-run by default.

Criteria are the ones written into the evidence report:
  product_match >= 10 and fired >= 20

Usage:
  python tools\promote_ord_evidence.py                # dry run
  python tools\promote_ord_evidence.py --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
EVID = ROOT / "reports" / "rule_evidence_combined_20261124.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default=str(EVID))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ev = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    promote = [x for x in ev["rows"] if x["proposed_provenance"] == "secondary"]
    print("criteria", ev["summary"].get("criteria"))
    print("to promote:", len(promote))
    for x in promote:
        print("  %-46s fired=%-6d match=%-5d dev=%d blind6=%d" %
              (x["id"], x["fired"], x["product_match"],
               x["dev_hits"], x["blind6_hits"]))
    if not args.apply:
        print("dry run; pass --apply to write rules.json")
        return 0

    d = json.loads(RULES.read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in d["rules"]}
    changed = 0
    for x in promote:
        r = by_id.get(x["id"])
        if r is None:
            continue
        if r.get("provenance") == "secondary":
            continue
        r["provenance"] = "secondary"
        changed += 1
    RULES.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("changed", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
