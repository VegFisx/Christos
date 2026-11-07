# -*- coding: utf-8 -*-
r"""一次性探针：走 **Wikipedia（zh）** 找中文名的学名（绕开 Wikidata）。"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from h2_fetch import fetch                                # noqa: E402

WIKI = "https://zh.wikipedia.org/w/api.php"
SCI = re.compile(r"学名[:：]?\s*([A-Z][a-z]{2,}\s+[a-z][a-z\-]{2,})")


def wiki_page(name: str) -> str:
    u = (WIKI + "?action=query&format=json&prop=extracts&explaintext=1"
         "&redirects=1&titles=" + urllib.parse.quote(name))
    d = json.loads(fetch(u, timeout=20))
    pages = (d.get("query") or {}).get("pages") or {}
    for _pid, p in pages.items():
        if "extract" in p:
            return p["extract"][:4000]
    return ""


for nm in ("甘草", "黄连", "丹参", "银杏", "龙胆", "大桫椤", "蜡瓣花"):
    t0 = time.time()
    try:
        txt = wiki_page(nm)
        m = SCI.search(txt)
        print("  %-6s → %s（%d 字，%.1fs）"
              % (nm, (m.group(1) if m else "（正文里没写学名）"), len(txt), time.time() - t0))
    except Exception as ex:                                # noqa: BLE001
        print("  %-6s ★ %s: %s" % (nm, type(ex).__name__, str(ex)[:60]))
    time.sleep(1.0)
