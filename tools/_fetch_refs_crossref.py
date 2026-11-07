# -*- coding: utf-8 -*-
# One-shot: pull metadata for the datasets the paper now depends on.
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
QUERIES = [
    "Therapeutics Data Commons machine learning datasets drug discovery",
    "Comparative Toxicogenomics Database update",
    "Tox21 ToxCast predictive toxicology",
    "BRENK filter PAINS frequent hitter",
]


def main() -> int:
    for q in QUERIES:
        url = ("https://api.crossref.org/works?rows=2&select=DOI,title,"
               "container-title,issued&query.bibliographic="
               + urllib.parse.quote(q))
        try:
            r = requests.get(url, proxies={"http": PROXY, "https": PROXY},
                             timeout=40)
            data = r.json()
        except Exception as ex:
            print("=== %s\n  ERR %s" % (q, type(ex).__name__))
            continue
        print("=== %s" % q)
        for it in data["message"]["items"]:
            title = (it.get("title") or [""])[0][:90]
            cont = (it.get("container-title") or [""])[0][:40]
            year = (it.get("issued", {}).get("date-parts", [[None]])[0][0])
            print("  %s | %s | %s | %s" % (it.get("DOI"), year, cont, title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
