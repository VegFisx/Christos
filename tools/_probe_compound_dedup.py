# -*- coding: utf-8 -*-
# One-shot: count how much duplication exists in the herb compound table.
# Read-only; never writes to the database.
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/tcm.db?mode=ro"


def q(cur, sql):
    cur.execute(sql)
    return cur.fetchone()[0]


def main() -> int:
    conn = sqlite3.connect(DB, uri=True)
    cur = conn.cursor()

    total = q(cur, "SELECT COUNT(*) FROM compounds")
    smi = q(cur, "SELECT COUNT(*) FROM compounds "
                 "WHERE smiles IS NOT NULL AND TRIM(smiles)<>''")
    smi_u = q(cur, "SELECT COUNT(DISTINCT smiles) FROM compounds "
                   "WHERE smiles IS NOT NULL AND TRIM(smiles)<>''")
    ik = q(cur, "SELECT COUNT(*) FROM compounds "
                "WHERE inchi_key IS NOT NULL AND TRIM(inchi_key)<>''")
    ik_u = q(cur, "SELECT COUNT(DISTINCT inchi_key) FROM compounds "
                  "WHERE inchi_key IS NOT NULL AND TRIM(inchi_key)<>''")
    links = q(cur, "SELECT COUNT(*) FROM herb_compound")
    herbs = q(cur, "SELECT COUNT(*) FROM herbs")

    print("compounds rows            %6d" % total)
    print("  with SMILES             %6d" % smi)
    print("  distinct SMILES         %6d" % smi_u)
    print("  with InChIKey           %6d" % ik)
    print("  distinct InChIKey       %6d" % ik_u)
    print("herb_compound links       %6d" % links)
    print("herbs rows                %6d" % herbs)
    if smi:
        print("duplication rate (SMILES) %.1f%%"
              % ((smi - smi_u) / smi * 100))

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
