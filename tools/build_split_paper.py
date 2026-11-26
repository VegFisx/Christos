# -*- coding: utf-8 -*-
"""把拆分稿（P1/P2）的 markdown 渲染成独立 HTML。

用法：
  python tools\\build_split_paper.py reports\\paper\\split-20261114\\P1-system.md
  python tools\\build_split_paper.py reports\\paper\\split-20261114\\P2-reranking-draft.md --title "P2"

输出 HTML 与 md 同目录，图片按 md 里的相对路径（figures/...）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "reports" / "paper" / "arxiv-20261020" / "paper-en.css"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--title", default=None)
    ap.add_argument("--css", default=str(CSS))
    a = ap.parse_args()

    src = Path(a.md).resolve()
    if not src.exists():
        print("[ERROR] 找不到 %s" % src)
        return 2
    out = src.with_suffix(".html")
    title = a.title or src.stem

    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    body = md.render(src.read_text(encoding="utf-8"))
    css = Path(a.css).read_text(encoding="utf-8") if Path(a.css).exists() else ""
    html = (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\" />\n"
        "<title>%s</title>\n<style>\n%s\n</style>\n</head>\n<body>\n%s\n</body>\n</html>\n"
        % (title, css, body)
    )
    out.write_text(html, encoding="utf-8")
    print("写出 %s（%.0f KB）" % (out, out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
