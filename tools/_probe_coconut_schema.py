# -*- coding: utf-8 -*-
import sqlite3, sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
con = sqlite3.connect("file:D:/TCMAI/coconut.db?mode=ro", uri=True)
cur = con.cursor()
for t in ("compounds", "genus_compound", "species_compound"):
    cols = [r[1] for r in cur.execute('PRAGMA table_info("%s")' % t)]
    print(t, "->", cols)
print("compounds 有空 SMILES 的:", cur.execute("SELECT COUNT(*) FROM compounds WHERE smiles IS NULL OR smiles = ''").fetchone()[0])
con.close()
