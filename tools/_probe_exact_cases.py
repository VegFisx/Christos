# -*- coding: utf-8 -*-
# One-shot: exact-name lookup for the conversion set.
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

NAMES = ["Aconitine", "Astragaloside iv", "Astragaloside IV",
         "Rutin", "Quercetin", "Ginsenoside rb1", "Ginsenoside rg3",
         "Benzoylaconine", "Aconine", "Glycyrrhizic acid"]


def main() -> int:
    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    for n in NAMES:
        cur.execute(
            "SELECT name_en, smiles FROM compounds "
            "WHERE lower(name_en)=lower(?) AND smiles IS NOT NULL LIMIT 1", (n,))
        r = cur.fetchone()
        if r:
            print("OK   %-20s %s" % (r[0][:20], (r[1] or "")[:56]))
        else:
            print("MISS %s" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
