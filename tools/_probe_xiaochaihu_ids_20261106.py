# -*- coding: utf-8 -*-
"""小柴胡汤所需的化合物/药材 id（只读）。"""
import sys, sqlite3
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/tcm.db?mode=ro"
NAMES = [
    "Saikosaponin A", "Saikosaponin D", "Saikosaponin a", "Saikosaponin d",
    "Saikogenin A", "Saikogenin D", "Saikogenin F", "Saikogenin G",
    "Baicalin", "Baicalein", "Wogonoside", "Wogonin",
    "Ginsenoside Rg1", "Ginsenoside Rb1", "Ginsenoside Re",
    "Glycyrrhizin", "Liquiritin",
]
HERBS = ["柴胡", "黄芩", "半夏", "人参", "甘草", "生姜", "大枣"]

con = sqlite3.connect(DB, uri=True)
cur = con.cursor()
for n in NAMES:
    rows = cur.execute(
        "SELECT ingredient_id,name_en,formula,inchi_key FROM compounds WHERE lower(name_en)=lower(?)",
        (n,)).fetchall()
    if not rows:
        rows = cur.execute(
            "SELECT ingredient_id,name_en,formula,inchi_key FROM compounds "
            "WHERE lower(name_en) LIKE lower(?) LIMIT 3", (n + "%",)).fetchall()
    print(f"- {n}: " + ("; ".join(f"{r[0]}|{r[1]}|{r[2]}|{(r[3] or '')[:14]}" for r in rows) if rows else "NOT FOUND"))

print()
for h in HERBS:
    rows = cur.execute("SELECT herb_id,name_cn FROM herbs WHERE name_cn=?", (h,)).fetchall()
    if not rows:
        rows = cur.execute("SELECT herb_id,name_cn FROM herbs WHERE name_cn LIKE ? LIMIT 2", (h + "%",)).fetchall()
    for hid, nm in rows:
        cnt = cur.execute("SELECT COUNT(*) FROM herb_compound WHERE herb_id=?", (hid,)).fetchone()[0]
        print(f"- {nm} {hid} compounds={cnt}")
    if not rows:
        print(f"- {h}: NOT FOUND")
con.close()
