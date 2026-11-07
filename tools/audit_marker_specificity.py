# -*- coding: utf-8 -*-
"""Score each compound by how many herbs it appears in.

Specificity is data-driven: a compound found in one or two herbs is
characteristic of those herbs; a compound found in dozens is common
machinery (sugars, amino acids) and carries no herb-level signal.

This needs no hand-written keyword table.
"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/tcm.db?mode=ro"


def main() -> int:
    cur = sqlite3.connect(DB, uri=True).cursor()

    cur.execute(
        "SELECT ingredient_id, COUNT(DISTINCT herb_id) FROM herb_compound "
        "GROUP BY ingredient_id")
    spread = {r[0]: r[1] for r in cur.fetchall()}

    cur.execute(
        "SELECT COUNT(DISTINCT ingredient_id) FROM herb_compound")
    total = cur.fetchone()[0]
    print("成分 %d 个，按出现药材数统计：" % total)

    buckets = [(1, 1), (2, 3), (4, 10), (11, 30), (31, 100), (101, 10 ** 6)]
    for lo, hi in buckets:
        n = sum(1 for v in spread.values() if lo <= v <= hi)
        print("  出现在 %3s~%-6s 个药材：%6d 个成分（%.1f%%）"
              % (lo, "∞" if hi > 10 ** 5 else hi, n, 100.0 * n / max(1, total)))

    for herb in ("甘草", "半夏", "麻黄"):
        cur.execute("SELECT herb_id FROM herbs WHERE name_cn=?", (herb,))
        r = cur.fetchone()
        if not r:
            continue
        cur.execute(
            "SELECT c.ingredient_id, c.name_en FROM herb_compound hc "
            "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id=?", (r[0],))
        rows = [(spread.get(i, 0), n) for i, n in cur.fetchall()]
        rows.sort()
        print("\n[%s] 全部 %d 个成分，按特异性取前 8：" % (herb, len(rows)))
        for sp, n in rows[:8]:
            print("   %-52s 出现于 %d 个药材" % (n[:52], sp))
        print("[%s] 最不特异的 5 个：" % herb)
        for sp, n in rows[-5:]:
            print("   %-52s 出现于 %d 个药材" % (n[:52], sp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
