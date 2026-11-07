# -*- coding: utf-8 -*-
# Render manuscript-humanized.md to standalone HTML.
#
# One-shot helper: the arXiv package was originally built with pandoc, which is
# not on PATH on this machine. markdown-it-py produces the same body structure
# and the existing paper-en.css supplies the print layout.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from markdown_it import MarkdownIt

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020")
SRC = ROOT / "manuscript-humanized.md"
CSS = ROOT / "paper-en.css"
OUT = ROOT / "manuscript-humanized.html"

md = MarkdownIt("commonmark", {"html": True}).enable("table")
body = md.render(SRC.read_text(encoding="utf-8"))

html = (
    "<!DOCTYPE html>\n"
    '<html lang="en">\n<head>\n<meta charset="utf-8" />\n'
    "<title>Christos arXiv manuscript</title>\n<style>\n"
    + CSS.read_text(encoding="utf-8")
    + "\n</style>\n</head>\n<body>\n"
    + body
    + "\n</body>\n</html>\n"
)

OUT.write_text(html, encoding="utf-8")
print("wrote %s (%d bytes)" % (OUT, len(html)))
