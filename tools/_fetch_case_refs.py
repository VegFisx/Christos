# -*- coding: utf-8 -*-
# One-shot: pull candidate references for the five known conversions.
import json
import sys
import urllib.parse

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROXY = "http://127.0.0.1:7897"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

QUERIES = [
    ("甘草酸→甘草次酸", "glycyrrhizic acid glycyrrhetinic acid hydrolysis"),
    ("人参皂苷Rb1→Rg3", "ginsenoside Rb1 Rg3 hydrolysis decoction"),
    ("乌头碱→苯甲酰乌头原碱", "aconitine benzoylaconine hydrolysis processing"),
    ("苯甲酰乌头原碱→乌头原碱", "benzoylaconine aconine hydrolysis"),
    ("芦丁→槲皮素", "rutin quercetin hydrolysis"),
]


def get(url):
    r = requests.get(url, proxies={"http": PROXY, "https": PROXY}, timeout=30)
    r.raise_for_status()
    return r.json()


def main() -> int:
    for label, q in QUERIES:
        url = "%s/esearch.fcgi?db=pubmed&term=%s&retmax=3&retmode=json" % (
            BASE, urllib.parse.quote(q))
        ids = get(url)["esearchresult"]["idlist"]
        print("=== %s  (%d hits)" % (label, len(ids)))
        if not ids:
            continue
        summ = get("%s/esummary.fcgi?db=pubmed&id=%s&retmode=json" % (
            BASE, ",".join(ids)))
        for pid in ids:
            d = summ["result"].get(pid) or {}
            authors = ", ".join(a["name"] for a in (d.get("authors") or [])[:3])
            print("  PMID %s | %s" % (pid, d.get("pubdate", "")))
            print("    %s" % (d.get("title", "")[:120]))
            print("    %s — %s" % (authors, d.get("source", "")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
