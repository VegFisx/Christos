# -*- coding: utf-8 -*-
"""一次性探针（只读）：tcm.db 的 ob_score / drug_likeness 能不能当"重要性"依据。"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TCM = r"D:\TCMAI\tcm.db"


def main() -> None:
    c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    tot = c.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    for col in ("ob_score", "drug_likeness"):
        nn = c.execute(f"SELECT COUNT(*) FROM compounds WHERE {col} IS NOT NULL "
                       f"AND {col} != ''").fetchone()[0]
        print("%-14s 非空 %6d / %d（%.1f%%）" % (col, nn, tot, 100.0 * nn / tot))
    print()
    print("甘草(HERB001779) 的 406 个成分里，有 OB/DL 的：")
    q = ("SELECT COUNT(*), SUM(CASE WHEN c.ob_score IS NOT NULL AND c.ob_score != '' "
         "THEN 1 ELSE 0 END), SUM(CASE WHEN c.drug_likeness IS NOT NULL "
         "AND c.drug_likeness != '' THEN 1 ELSE 0 END) "
         "FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
         "WHERE hc.herb_id='HERB001779'")
    n, n_ob, n_dl = c.execute(q).fetchone()
    print("   总 %d · 有 OB %s · 有 DL %s" % (n, n_ob, n_dl))
    print()
    print("按 OB 降序前 8（甘草）：")
    q2 = ("SELECT c.name_en, c.ob_score, c.drug_likeness, hc.match_level "
          "FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
          "WHERE hc.herb_id='HERB001779' AND c.ob_score IS NOT NULL AND c.ob_score != '' "
          "ORDER BY CAST(c.ob_score AS REAL) DESC LIMIT 8")
    for nm, ob, dl, lv in c.execute(q2):
        print("   %-38s OB=%-6s DL=%-6s %s" % (str(nm)[:38], ob, dl, lv))
    print()
    print("TCMSP 经典口径（OB>=30 且 DL>=0.18）在甘草里命中多少：")
    q3 = ("SELECT COUNT(*) FROM herb_compound hc JOIN compounds c "
          "ON hc.ingredient_id=c.ingredient_id WHERE hc.herb_id='HERB001779' "
          "AND CAST(c.ob_score AS REAL)>=30 AND CAST(c.drug_likeness AS REAL)>=0.18")
    print("   ", c.execute(q3).fetchone()[0])
    c.close()


if __name__ == "__main__":
    main()
