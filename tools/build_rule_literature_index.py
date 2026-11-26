# -*- coding: utf-8 -*-
"""Verify DOIs already in rule notes and fetch candidate references.

- DOIs found in rules.json notes are resolved through the Crossref API and
  stored as `verified_doi` records (title/journal/year from Crossref).
- A small hand-picked list of high-usage rules without a citation gets a
  Crossref bibliographic search; those records are `candidate` only.

Never edits rules.json.  Output: reports/rule_literature_20261124.json/.md
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
OUT_JSON = ROOT / "reports" / "rule_literature_20261124.json"
OUT_MD = ROOT / "reports" / "rule_literature_20261124.md"
DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")

QUERIES = [
    ("oxidation_sulfide_001",
     "oxidation of sulfides to sulfoxides hydrogen peroxide"),
    ("substitution_alcohol_thionyl_family_001",
     "thionyl chloride conversion of alcohols to alkyl chlorides"),
    ("acylation_alcohol_anhydride_001",
     "acylation of alcohols with carboxylic acid anhydrides"),
    ("aminolysis_ester_001",
     "aminolysis of esters with amines"),
    ("hydration_alkene_001",
     "acid catalyzed hydration of alkenes"),
    ("hydrolysis_imine_001",
     "hydrolysis of imines Schiff bases"),
    ("oxidation_epoxide_001",
     "epoxidation of alkenes with peroxy acids"),
    ("oxidation_aldehyde_001",
     "oxidation of aldehydes to carboxylic acids"),
]


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "chemreact-evidence/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def work_meta(doi: str):
    d = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
    return {
        "doi": doi,
        "title": (d.get("title") or [""])[0],
        "container": (d.get("container-title") or [""])[0],
        "year": ((d.get("issued") or {}).get("date-parts") or [[None]])[0][0],
    }


def main() -> int:
    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = {r["id"]: r for r in d["rules"]}

    verified = []
    for r in d["rules"]:
        if str(r.get("status") or "active") != "active":
            continue
        if str(r.get("provenance") or "unvalidated") != "unvalidated":
            continue
        for doi in DOI.findall(r.get("notes") or ""):
            doi = doi.rstrip(").,;")
            try:
                m = work_meta(doi)
            except Exception as exc:
                verified.append({"rule": r["id"], "doi": doi,
                                 "status": "doi_unresolved",
                                 "error": "%s %s" % (type(exc).__name__, exc)})
                continue
            m.update({"rule": r["id"], "status": "verified_doi"})
            verified.append(m)
            print("verified", r["id"], m.get("year"), m.get("title")[:70])
            time.sleep(0.2)

    candidates = []
    for rid, q in QUERIES:
        if rid not in rules:
            continue
        url = ("https://api.crossref.org/works?rows=3&select=DOI,title,"
               "container-title,issued,type&query.bibliographic="
               + urllib.parse.quote(q))
        try:
            items = get(url)["message"]["items"]
        except Exception as exc:
            candidates.append({"rule": rid, "query": q, "status": "query_failed",
                               "error": "%s %s" % (type(exc).__name__, exc)})
            continue
        picks = []
        for it in items:
            picks.append({
                "doi": it.get("DOI"),
                "title": (it.get("title") or [""])[0],
                "container": (it.get("container-title") or [""])[0],
                "year": ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0],
                "type": it.get("type"),
            })
        candidates.append({"rule": rid, "query": q, "status": "candidate",
                           "picks": picks})
        print("candidate", rid, "->", (picks[0]["title"][:70] if picks else "none"))
        time.sleep(0.2)

    OUT_JSON.write_text(json.dumps({"verified": verified, "candidates": candidates},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Rule literature index", "",
             "`verified_doi` = DOI already present in the rule notes, resolved via "
             "Crossref (metadata checked). `candidate` = Crossref keyword search "
             "for a high-usage rule with no citation; **not read, not verified**.", "",
             "## Verified DOIs", ""]
    for x in verified:
        if x["status"] == "verified_doi":
            lines.append("- `%s` — %s (%s, %s) DOI `%s`" %
                         (x["rule"], x["title"], x["container"], x["year"], x["doi"]))
        else:
            lines.append("- `%s` — DOI `%s` **未解析**: %s" %
                         (x["rule"], x["doi"], x.get("error")))
    lines += ["", "## Candidates (unverified)", ""]
    for c in candidates:
        if c["status"] != "candidate":
            lines.append("- `%s` — 查询失败: %s" % (c["rule"], c.get("error")))
            continue
        lines.append("### `%s`" % c["rule"])
        lines.append("query: %s" % c["query"])
        for p in c["picks"]:
            lines.append("- %s (%s, %s) DOI `%s`" %
                         (p["title"], p["container"], p["year"], p["doi"]))
        lines.append("")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("verified", sum(1 for x in verified if x["status"] == "verified_doi"),
          "/", len(verified), "candidate rules", len(candidates))
    print("written", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
