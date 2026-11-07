# -*- coding: utf-8 -*-
"""Search the official arXiv API for work related to the Christos system paper.

Raw Atom XML is preserved so that every reported title/ID can be checked
without relying on a search-result snippet.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
OUT = STAGE / "reports" / "paper" / "arxiv_search_20261020"
ATOM = "http://www.w3.org/2005/Atom"

QUERIES = {
    "template_retrosynthesis": 'all:"retrosynthesis" AND all:"template"',
    "reaction_provenance": 'all:"reaction prediction" AND all:"provenance"',
    "tcm_reaction_prediction": 'all:"traditional Chinese medicine" AND all:"reaction prediction"',
    "template_quality": 'all:"reaction template" AND all:"quality"',
    "retrosynthesis_benchmark": 'all:"retrosynthesis" AND all:"benchmark"',
    "template_audit": 'all:"template" AND all:"reaction" AND all:"audit"',
    "chemical_provenance": 'all:"chemical reaction" AND all:"provenance"',
    "christos_name": 'all:"Christos" AND all:"reaction"',
    "reaction_software": 'all:"reaction prediction" AND all:"software"',
    "retro_provenance": 'all:"retrosynthesis" AND all:"provenance"',
    "tcm_broad": 'all:"Chinese medicine" AND all:"reaction"',
    "reaction_template_audit": 'all:"reaction template" AND all:"audit"',
    "syntheseus": 'all:"Syntheseus"',
    "reaction_template_benchmark": 'all:"reaction template" AND all:"benchmark"',
}


def text(node):
    return " ".join((node.text or "").split()) if node is not None else ""


def fetch(query: str):
    params = urllib.parse.urlencode({
        "search_query": query,
        "start": 0,
        "max_results": 20,
        "sortBy": "relevance",
        "sortOrder": "descending",
    })
    url = "https://export.arxiv.org/api/query?" + params
    req = urllib.request.Request(url, headers={
        "User-Agent": "Christos-arXiv-related-search/0.9",
    })
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - preserve retry failures
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    failures = []
    for name, query in QUERIES.items():
        try:
            xml = fetch(query)
        except Exception as exc:  # noqa: BLE001
            failures.append({"query": name, "error": f"{type(exc).__name__}: {exc}"})
            print("FAIL", name, exc)
            continue
        (OUT / f"{name}.xml").write_text(xml, encoding="utf-8")
        root = ET.fromstring(xml)
        rows = []
        for entry in root.findall(f"{{{ATOM}}}entry"):
            link = ""
            for ln in entry.findall(f"{{{ATOM}}}link"):
                if ln.get("rel") == "alternate":
                    link = ln.get("href") or ""
            row = {
                "query": name,
                "id": text(entry.find(f"{{{ATOM}}}id")),
                "title": text(entry.find(f"{{{ATOM}}}title")),
                "published": text(entry.find(f"{{{ATOM}}}published")),
                "updated": text(entry.find(f"{{{ATOM}}}updated")),
                "url": link,
                "authors": [text(a.find(f"{{{ATOM}}}name"))
                            for a in entry.findall(f"{{{ATOM}}}author")],
                "summary": text(entry.find(f"{{{ATOM}}}summary")),
                "primary_category": (
                    entry.find(f"{{{ATOM}}}primary_category").get("term", "")
                    if entry.find(f"{{{ATOM}}}primary_category") is not None else ""
                ),
            }
            rows.append(row)
            all_rows.append(row)
        print(f"{name}: {len(rows)} results")
        time.sleep(2)

    # Deduplicate by arXiv id, preferring the first (relevance) occurrence.
    unique = {}
    for row in all_rows:
        unique.setdefault(row["id"], row)
    (OUT / "results.json").write_text(
        json.dumps({"queries": QUERIES, "results": list(unique.values()),
                    "failures": failures}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"total unique={len(unique)} failures={len(failures)}")
    for row in list(unique.values())[:15]:
        print(row["id"].rsplit("/", 1)[-1], "|", row["published"][:10], "|", row["title"])
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
