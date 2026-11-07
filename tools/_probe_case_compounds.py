# -*- coding: utf-8 -*-
# One-shot: locate substrate/product SMILES for five literature conversions.
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WANT = [
    "glycyrrhizic", "glycyrrhetinic",
    "astragaloside", "cycloastragenol",
    "aconitine", "benzoylaconine", "aconine",
    "rutin", "quercetin",
    "ginsenoside rb1", "ginsenoside rg3",
]


def main() -> int:
    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    for w in WANT:
        cur.execute(
            "SELECT name_en, smiles FROM compounds "
            "WHERE lower(name_en) LIKE ? AND smiles IS NOT NULL LIMIT 3",
            ("%" + w + "%",),
        )
        rows = cur.fetchall()
        print("%-18s -> %d" % (w, len(rows)))
        for n, s in rows:
            print("    %-42s %s" % (n[:42], (s or "")[:64]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
