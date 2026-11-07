# -*- coding: utf-8 -*-
import sqlite3, sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "D:/TCMAI/tcm.db"
NAMES = ["桔梗", "荆芥", "紫菀", "百部", "白前", "甘草", "陈皮"]
con = sqlite3.connect(DB); cur = con.cursor()
print("tables:", [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")])
tot = set()
for nm in NAMES:
    rows = cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn = ?", (nm,)).fetchall()
    if not rows:
        rows = cur.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ?", ("%" + nm + "%",)).fetchall()[:3]
    if not rows:
        print("  %s -> 查不到" % nm); continue
    for hid, cn in rows:
        ids = [r[0] for r in cur.execute("SELECT ingredient_id FROM herb_compound WHERE herb_id = ?", (hid,))]
        ok = cur.execute("SELECT COUNT(*) FROM compounds WHERE ingredient_id IN (SELECT ingredient_id FROM herb_compound WHERE herb_id=?) AND smiles IS NOT NULL AND smiles <> ''", (hid,)).fetchone()[0]
        tot.update(ids)
        print("  %-6s id=%-7s 成分 %4d / 有SMILES %4d" % (cn, hid, len(ids), ok))
print("去重成分 %d" % len(tot))
if tot:
    q = ",".join("?" * len(tot))
    n = cur.execute("SELECT COUNT(*) FROM compounds WHERE ingredient_id IN (%s) AND smiles IS NOT NULL AND smiles <> ''" % q, list(tot)).fetchone()[0]
    print("去重后有 SMILES 的 %d" % n)
con.close()
