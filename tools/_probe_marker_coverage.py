# -*- coding: utf-8 -*-
# One-shot: how many marker compounds does each limit actually cover?
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERB = "甘草"


def main() -> int:
    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    cur.execute("SELECT herb_id FROM herbs WHERE name_cn=?", (HERB,))
    r = cur.fetchone()
    if not r:
        print("herb not found")
        return 2
    hid = r[0]

    cur.execute(
        "SELECT c.ingredient_id, c.name_en, c.mol_weight, hc.match_level "
        "FROM herb_compound hc JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
        "WHERE hc.herb_id=? AND c.smiles IS NOT NULL AND c.smiles<>'' "
        "ORDER BY CASE hc.match_level WHEN 'marker' THEN 0 ELSE 1 END, "
        "c.mol_weight DESC", (hid,))
    rows = cur.fetchall()
    total = len(rows)
    markers = [x for x in rows if x[3] == "marker"]
    print("%s：%d 个成分，其中 marker %d 个" % (HERB, total, len(markers)))

    for lim in (3, 6, 12, 24, 48):
        head = rows[:lim]
        m = sum(1 for x in head if x[3] == "marker")
        share_total = 100.0 * len(head) / total
        share_marker = 100.0 * m / max(1, len(markers))
        print("  limit %2d：覆盖成分 %5.1f%%（%d/%d），覆盖 marker %5.1f%%（%d/%d）"
              % (lim, share_total, len(head), total,
                 share_marker, m, len(markers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
