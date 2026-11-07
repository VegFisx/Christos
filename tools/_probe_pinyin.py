# -*- coding: utf-8 -*-
"""一次性探针：核对 gancao 这类拼音在 herbs.pinyin 里的实际写法。"""
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
q = ("SELECT herb_id, name_cn, pinyin FROM herbs "
     "WHERE pinyin LIKE '%gancao%' OR name_cn = '甘草' ORDER BY herb_id LIMIT 20")
for r in c.execute(q):
    print(r)
c.close()
