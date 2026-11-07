# -*- coding: utf-8 -*-
"""Download a Frontiers article HTML and print processing-chemistry sentences.

Downloads go to reports/_paozhi_src/; this script stays in tools/.

Usage:
  python -I tools/fetch_paozhi_html.py <url> <slug>
"""
import html
import re
import sys
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/reports/_paozhi_src")
KEYS = re.compile(
    r"hydroly|dehydrat|maillard|isomeriz|aglycone|glycosid|steam|"
    r"conjugat|condensat|deglycosyl|anthraquinone|stilbene",
    re.I,
)


def clean(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style).*?</\1>", " ", fragment)
    fragment = re.sub(r"(?s)<[^>]+>", " ", fragment)
    fragment = html.unescape(fragment)
    return re.sub(r"\s+", " ", fragment).strip()


def main(url: str, slug: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    dest = OUT / f"{slug}.html"
    dest.write_text(data, encoding="utf-8")

    title = re.search(r"(?is)<title>(.*?)</title>", data)
    print(f"{slug} | {clean(title.group(1)) if title else ''}")
    for m in re.finditer(r'(?is)<meta[^>]+(?:name|property)="(citation_doi|citation_journal_title|citation_publication_date)"[^>]+content="([^"]*)"', data):
        print(f"  {m.group(1)}={m.group(2)}")

    paragraphs = re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", data)
    hits = 0
    for raw in paragraphs:
        txt = clean(raw)
        if len(txt) < 40:
            continue
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", txt):
            if KEYS.search(sent):
                hits += 1
                if hits <= 60:
                    print(f"  - {sent}")
    print(f"  -- {hits} matching sentence(s); file={dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
