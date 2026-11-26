# -*- coding: utf-8 -*-
"""Combine ORD execution evidence and verified literature into one table.

Inputs (all produced by other tools):
  reports/rule_ord_execution_*.json     audit_rules_against_ord_reactions.py
  reports/rule_literature_*.json        build_rule_literature_index.py
  reports/evidence_backlog_*.json       audit_evidence_backlog.py

Grades per active unvalidated rule:
  strong_ord   product_match >= 10 and fired >= 20
  weak_ord     product_match >= 1
  no_ord       fired == 0 or product_match == 0
  lit          a DOI in the notes was verified by Crossref

Proposed provenance:
  secondary    strong_ord (data-derived, not literature)
  cited        lit and weak_ord (both a reference and an execution)
  keep         everything else

This tool never edits rules.json.
"""
from __future__ import annotations

import glob
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
OUT_JSON = ROOT / "reports" / "rule_evidence_combined_20261124.json"
OUT_MD = ROOT / "reports" / "rule_evidence_combined_20261124.md"

STRONG_MATCH = 10
STRONG_FIRED = 20


def latest(pattern):
    fs = glob.glob(str(ROOT / pattern))
    return max(fs, key=lambda p: Path(p).stat().st_mtime) if fs else None


def load_rows(path, key="rows"):
    if not path or not Path(path).exists():
        return []
    return json.loads(Path(path).read_text(encoding="utf-8")).get(key) or []


def main() -> int:
    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = {r["id"]: r for r in d["rules"]}
    unv = [r for r in d["rules"]
           if str(r.get("status") or "active") == "active"
           and str(r.get("provenance") or "unvalidated") == "unvalidated"]

    ord_f = latest("reports/rule_ord_execution_*.json")
    lit_f = latest("reports/rule_literature_*.json")
    use_f = latest("reports/evidence_backlog_*.json")

    ord_rows = {x.get("id"): x for x in load_rows(ord_f)}
    lit = json.loads(Path(lit_f).read_text(encoding="utf-8")) if lit_f else {}
    verified = {}
    for x in lit.get("verified") or []:
        if x.get("status") == "verified_doi":
            verified.setdefault(x["rule"], []).append(x)
    usage = {x["id"]: x for x in load_rows(use_f)}

    out = []
    for r in unv:
        rid = r["id"]
        o = ord_rows.get(rid) or {}
        fired = int(o.get("fired") or 0)
        match = int(o.get("product_match") or 0)
        u = usage.get(rid) or {}
        if match >= STRONG_MATCH and fired >= STRONG_FIRED:
            grade = "strong_ord"
        elif match >= 1:
            grade = "weak_ord"
        else:
            grade = "no_ord"
        has_lit = rid in verified
        if grade == "strong_ord":
            proposal = "secondary"
        elif has_lit and grade == "weak_ord":
            proposal = "cited"
        else:
            proposal = "keep"
        out.append({
            "id": rid,
            "category": r.get("category"),
            "fired": fired,
            "product_match": match,
            "ord_grade": grade,
            "literature": [
                {"doi": x.get("doi"), "title": x.get("title"),
                 "container": x.get("container"), "year": x.get("year")}
                for x in verified.get(rid, [])
            ],
            "dev_hits": u.get("dev_hits", 0),
            "blind6_hits": u.get("blind6_hits", 0),
            "examples": (o.get("examples_match") or [])[:3],
            "proposed_provenance": proposal,
        })

    out.sort(key=lambda x: (-x["product_match"], x["id"]))
    summary = {
        "rules": len(out),
        "strong_ord": sum(1 for x in out if x["ord_grade"] == "strong_ord"),
        "weak_ord": sum(1 for x in out if x["ord_grade"] == "weak_ord"),
        "no_ord": sum(1 for x in out if x["ord_grade"] == "no_ord"),
        "with_literature": sum(1 for x in out if x["literature"]),
        "propose_secondary": sum(1 for x in out if x["proposed_provenance"] == "secondary"),
        "propose_cited": sum(1 for x in out if x["proposed_provenance"] == "cited"),
        "keep": sum(1 for x in out if x["proposed_provenance"] == "keep"),
        "ord_file": Path(ord_f).name if ord_f else None,
        "lit_file": Path(lit_f).name if lit_f else None,
        "usage_file": Path(use_f).name if use_f else None,
        "criteria": {"strong_match": STRONG_MATCH, "strong_fired": STRONG_FIRED},
    }
    OUT_JSON.write_text(json.dumps({"summary": summary, "rows": out},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Combined rule evidence", "",
             "- active unvalidated: **%d**" % len(out),
             "- strong ORD (match>=%d, fired>=%d): **%d**"
             % (STRONG_MATCH, STRONG_FIRED, summary["strong_ord"]),
             "- weak ORD: **%d**" % summary["weak_ord"],
             "- no ORD execution: **%d**" % summary["no_ord"],
             "- with verified literature: **%d**" % summary["with_literature"],
             "- proposed: secondary %d / cited %d / keep %d"
             % (summary["propose_secondary"], summary["propose_cited"],
                summary["keep"]), "",
             "| rule | fired | product match | ORD | lit | dev | blind6 | propose |",
             "|---|---:|---:|---|---|---:|---:|---|"]
    for x in out:
        lines.append("| `%s` | %d | %d | %s | %s | %d | %d | %s |" %
                     (x["id"], x["fired"], x["product_match"], x["ord_grade"],
                      x["literature"][0]["doi"] if x["literature"] else "",
                      x["dev_hits"], x["blind6_hits"],
                      x["proposed_provenance"]))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print("written", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
