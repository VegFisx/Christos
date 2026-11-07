# -*- coding: utf-8 -*-
# Render the Chinese humanized manuscript to standalone HTML.
#
# Same approach as the English build: pandoc is not on PATH, so markdown-it-py
# supplies the body and paper-zh.css supplies the print layout.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from markdown_it import MarkdownIt

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper")
SRC = ROOT / "Christos-system-paper-draft-20261019-zh-humanized.md"
CSS = ROOT / "paper-zh.css"
OUT = ROOT / "Christos-system-paper-draft-20261019-zh-humanized.html"

md = MarkdownIt("commonmark", {"html": True}).enable("table")
body = md.render(SRC.read_text(encoding="utf-8"))

html = (
    "<!DOCTYPE html>\n"
    '<html lang="zh-CN">\n<head>\n<meta charset="utf-8" />\n'
    "<title>Christos 系统论文（中文人味版）</title>\n<style>\n"
    + CSS.read_text(encoding="utf-8")
    + "\n</style>\n</head>\n<body>\n"
    + body
    + "\n</body>\n</html>\n"
)

OUT.write_text(html, encoding="utf-8")
print("wrote %s (%d bytes)" % (OUT, len(html)))
