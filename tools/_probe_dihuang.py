# -*- coding: utf-8 -*-
"""一次性探针：地黄类与龙胆类药材在库里的实际名字。"""
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
for kw in ("地黄", "龙胆", "延胡索", "槐"):
    rows = [r[0] for r in c.execute(
        "SELECT name_cn FROM herbs WHERE name_cn LIKE ? LIMIT 14", ("%" + kw + "%",))]
    print("含「%s」→ %s" % (kw, rows))
c.close()
