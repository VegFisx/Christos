# -*- coding: utf-8 -*-
"""Read-only probe #2: compounds linked to 醋 / 醋酸 herbs; exact rows for selected IDs."""
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

con = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

for hid in ("HERB000960", "HERB000987", "HERB005018", "HERB005096", "HERB002538"):
    h = cur.execute("SELECT herb_id,name_cn,name_en FROM herbs WHERE herb_id=?", (hid,)).fetchone()
    if not h:
        print(f"  {hid}: no herb")
        continue
    rows = cur.execute(
        "SELECT c.ingredient_id, c.name_en, c.formula, c.pubchem_id, "
        "COALESCE(c.isomeric_smiles, c.smiles) AS smi, hc.match_level "
        "FROM herb_compound hc JOIN compounds c ON c.ingredient_id=hc.ingredient_id "
        "WHERE hc.herb_id=? LIMIT 20", (hid,)
    ).fetchall()
    print(f"== {hid} {h['name_cn']} / {h['name_en']} : {len(rows)} compound(s)")
    for r in rows:
        print(f"   {r['ingredient_id']} | {r['name_en']} | {r['formula']} | pubchem={r['pubchem_id']} | {r['smi']}")

print("== exact rows ==")
for iid in ("HBIN028037", "HBIN026793", "HBIN015097", "HBIN044247", "HBIN045073"):
    r = cur.execute(
        "SELECT ingredient_id,name_en,formula,smiles,isomeric_smiles,pubchem_id "
        "FROM compounds WHERE ingredient_id=?", (iid,)
    ).fetchone()
    print(dict(r) if r else f"{iid}: none")

con.close()
