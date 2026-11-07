# -*- coding: utf-8 -*-
"""Fetch open-access full texts from Europe PMC and print only the sentences
that mention processing chemistry (hydrolysis / dehydration / Maillard ...).

Downloads go to reports/_paozhi_src/ (their own directory); this script stays in
tools/ and only reads those files.

Usage:
  python -I tools/fetch_paozhi_fulltexts.py PMC6121093 PMC11335691
"""
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/reports/_paozhi_src")

KEYS = re.compile(
    r"hydroly|dehydrat|maillard|isomeriz|aglycone|glycosid|steam|process|"
    r"conjugat|condensat|deglycosyl|anthraquinone|stilbene",
    re.I,
)


def text_of(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    for pmcid in argv:
        url = f"{BASE}/{pmcid}/fullTextXML"
        dest = OUT / f"{pmcid}.xml"
        try:
            data = urllib.request.urlopen(url, timeout=40).read()
            dest.write_bytes(data)
        except Exception as ex:
            print(f"!! {pmcid}: download failed: {type(ex).__name__}: {ex}")
            continue
        try:
            root = ET.fromstring(data)
        except Exception as ex:
            print(f"!! {pmcid}: XML parse failed: {type(ex).__name__}: {ex}")
            continue

        def find_text(tag):
            el = root.find(f".//{tag}")
            return text_of(el) if el is not None else ""

        print("=" * 100)
        print(f"{pmcid} | {find_text('article-title')}")
        print(f"  journal={find_text('journal-title')} year={find_text('pub-date/year')}")
        for aid in root.findall(".//article-id"):
            if aid.get("pub-id-type") in ("doi", "pmcid"):
                print(f"  {aid.get('pub-id-type')}={text_of(aid)}")

        hits = 0
        for sec in root.iter("sec"):
            st = sec.find("title")
            sec_title = text_of(st) if st is not None else ""
            for p in sec.findall("p"):
                raw = text_of(p)
                if not raw:
                    continue
                for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", raw):
                    if KEYS.search(sent) and len(sent) > 40:
                        hits += 1
                        if hits <= 60:
                            print(f"  [{sec_title[:40]}] {sent}")
        print(f"  -- {hits} matching sentence(s); file={dest}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["PMC6121093", "PMC11335691"])
