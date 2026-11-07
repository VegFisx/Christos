# -*- coding: utf-8 -*-
"""Compare the hand-written marker table against the pharmacopoeial markers.

The hand-written table is built by keyword LIKE matching; the pharmacopoeial one
comes from the 2025 edition's assay and identification sections.  Agreement
between them is the only cheap quality signal available offline.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
sys.path.insert(0, str(STAGE / "sources"))

import chp_priority as CP  # noqa: E402

HERBS = ["甘草", "人参", "黄芪", "黄连", "大黄", "麻黄", "黄芩", "丹参", "当归", "半夏"]


def main() -> int:
    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    chp = CP.load_map()

    print("%-6s %8s %8s %8s %8s" % ("药材", "手写", "药典", "交集", "仅手写"))
    for h in HERBS:
        cur.execute("SELECT herb_id FROM herbs WHERE name_cn=?", (h,))
        r = cur.fetchone()
        if not r:
            continue
        hid = r[0]
        cur.execute(
            "SELECT c.name_en FROM herb_compound hc "
            "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id=? AND hc.match_level='marker'", (hid,))
        hand = {x[0] for x in cur.fetchall() if x[0]}

        ph = chp.get(h) or {}
        ph_names = {v[3] for v in ph.values() if v and len(v) > 3 and v[3]}

        inter = hand & ph_names
        only_hand = hand - ph_names
        print("%-6s %8d %8d %8d %8d"
              % (h, len(hand), len(ph_names), len(inter), len(only_hand)))
        if only_hand and len(only_hand) <= 6:
            print("       仅手写：%s" % ", ".join(sorted(only_hand))[:90])
    print("\n=== 名称格式对照（甘草 / 半夏）")
    for h in ("甘草", "半夏"):
        cur.execute("SELECT herb_id FROM herbs WHERE name_cn=?", (h,))
        r = cur.fetchone()
        if not r:
            continue
        hid = r[0]
        print("[%s] 药典条目：" % h)
        for k, v in list((chp.get(h) or {}).items())[:4]:
            print("    %s" % (v,))
        print("[%s] 手写成分：" % h)
        cur.execute(
            "SELECT c.name_en FROM herb_compound hc "
            "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id=? AND hc.match_level='marker' LIMIT 4", (hid,))
        for (nm,) in cur.fetchall():
            print("    %s" % nm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
