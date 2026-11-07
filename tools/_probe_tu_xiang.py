# -*- coding: utf-8 -*-
"""一次性探针：土木香/土茯苓这类"名字带土"的到底是不是炮制品。"""
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\sources")
import herb_species as HS  # noqa: E402

c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
names = {r[0]: r[1] for r in c.execute("SELECT name_cn, herb_id FROM herbs")}
c.close()
for k in ("土木香", "木香", "土茯苓", "茯苓", "姜半夏", "半夏", "制何首乌", "何首乌",
          "炙甘草", "甘草"):
    print("%-8s 在库=%-14s 药典物种=%s"
          % (k, names.get(k, "—"), HS.species_of(k) or "（无）"))
