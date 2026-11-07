# -*- coding: utf-8 -*-
r"""一次性探针：coconut.db 的真实列名 + 这 4 味在库里到底有没有。"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

c = sqlite3.connect("file:D:/TCMAI/coconut.db?mode=ro", uri=True)
for t in ("compounds", "species_compound", "genus_compound"):
    cols = [r[1] for r in c.execute("PRAGMA table_info(%s)" % t).fetchall()]
    n = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    print("%-16s %7d 行 ｜ 列：%s" % (t, n, ", ".join(cols)))

print()
q = "SELECT DISTINCT species FROM species_compound WHERE lower(species) LIKE ? LIMIT 6"
for kw in ("gendarussa", "hana", "rana", "dybowskii", "turpinia", "polygonum perfoliatum"):
    try:
        rows = c.execute(q, ("%" + kw + "%",)).fetchall()
        print("  species like %-20s → %s" % (kw, [r[0] for r in rows] or "（无）"))
    except Exception as ex:                                # noqa: BLE001
        print("  查询失败：%s" % ex)
c.close()
