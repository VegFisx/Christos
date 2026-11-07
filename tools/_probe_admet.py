# -*- coding: utf-8 -*-
# One-shot: what is inside the ADMET cache?
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/data/admet_cache.db?mode=ro"


def main() -> int:
    cur = sqlite3.connect(DB, uri=True).cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print("tables:", tables)
    for t in tables:
        cur.execute('SELECT COUNT(*) FROM "%s"' % t)
        n = cur.fetchone()[0]
        cur.execute('PRAGMA table_info("%s")' % t)
        cols = [r[1] for r in cur.fetchall()]
        print("\n%s: %d rows" % (t, n))
        print("  cols:", cols[:24])
        if n:
            cur.execute('SELECT * FROM "%s" LIMIT 2' % t)
            for r in cur.fetchall():
                print("  sample:", str(r)[:240])
        if t == "admet":
            import json
            cur.execute('SELECT data FROM admet LIMIT 1')
            d = json.loads(cur.fetchone()[0])
            print("  keys:", sorted(d.keys()))
            for k in ("LD50_Zhu", "LD50_Zhu_drugbank_approved_percentile",
                      "hERG", "hERG_drugbank_approved_percentile",
                      "DILI", "DILI_drugbank_approved_percentile"):
                print("    %-46s = %r" % (k, d.get(k)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
