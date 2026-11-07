# -*- coding: utf-8 -*-
import sqlite3, sys, glob, os
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
DBS = ["D:/TCMAI/tcm.db", "D:/TCMAI/coconut.db",
       "D:/TCMAI/backups/tcm_final.db", "D:/TCMAI/archive/deprecated/tcm_before_cleanup.db",
       "D:/TCMAI/data/admet_cache.db"]
for db in DBS:
    if not os.path.exists(db):
        print(db, "MISSING"); continue
    con = sqlite3.connect("file:" + db + "?mode=ro", uri=True)
    cur = con.cursor()
    rows = cur.execute("SELECT type, name FROM sqlite_master ORDER BY type, name").fetchall()
    print("")
    print("== %s（%d 个对象）" % (db, len(rows)))
    for t, n in rows:
        if t in ("table", "view"):
            try:
                c = cur.execute('SELECT COUNT(*) FROM "%s"' % n).fetchone()[0]
            except Exception as e:
                c = -1
            print("   %-6s %-28s %s 行" % (t, n, c))
    con.close()
