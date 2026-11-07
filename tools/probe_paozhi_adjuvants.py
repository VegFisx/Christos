# -*- coding: utf-8 -*-
"""Read-only probe: adjuvant / co-substrate candidates in tcm.db.

Answers only:
  - which herbs match 蜂蜜 / 黄酒 / 米醋 / 生姜 / 食盐
  - which compound rows match glucose / fructose / ethanol / acetic acid
  - the SMILES + provenance columns for those rows

Usage:
  python tools/probe_paozhi_adjuvants.py
"""
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/tcm.db?mode=ro"

HERB_TERMS = ["蜂蜜", "蜜", "黄酒", "米醋", "醋", "生姜", "姜", "食盐", "盐"]
COMP_TERMS = ["glucose", "fructose", "ethanol", "acetic acid", "sucrose", "maltose"]


def main() -> None:
    con = sqlite3.connect(DB, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print("== herbs matching adjuvant terms ==")
    for term in HERB_TERMS:
        rows = cur.execute(
            "SELECT herb_id, name_cn, name_en, pinyin FROM herbs "
            "WHERE name_cn LIKE ? OR alias LIKE ? LIMIT 8",
            (f"%{term}%", f"%{term}%"),
        ).fetchall()
        print(f"  [{term}] {len(rows)} hit(s)")
        for r in rows:
            print(f"    {r['herb_id']:>6}  {r['name_cn']} | {r['name_en']} | {r['pinyin']}")

    print("== compounds matching co-substrate terms (name_en/alias) ==")
    for term in COMP_TERMS:
        rows = cur.execute(
            "SELECT ingredient_id, name_en, alias, formula, pubchem_id, smiles, isomeric_smiles "
            "FROM compounds WHERE lower(name_en) = ? OR lower(alias) = ? "
            "OR lower(name_en) LIKE ? LIMIT 8",
            (term, term, f"%{term}%"),
        ).fetchall()
        print(f"  [{term}] {len(rows)} hit(s)")
        for r in rows:
            smi = r["isomeric_smiles"] or r["smiles"] or ""
            print(f"    id={r['ingredient_id']} name={r['name_en']!r} formula={r['formula']} "
                  f"pubchem={r['pubchem_id']} smiles={smi[:90]}")

    print("== compounds linked to matched herbs (first 3 herbs) ==")
    for term in ["蜂蜜", "黄酒", "米醋", "生姜", "食盐"]:
        herbs = cur.execute(
            "SELECT herb_id, name_cn FROM herbs WHERE name_cn = ? LIMIT 1", (term,)
        ).fetchall()
        if not herbs:
            herbs = cur.execute(
                "SELECT herb_id, name_cn FROM herbs WHERE name_cn LIKE ? LIMIT 1",
                (f"%{term}%",),
            ).fetchall()
        if not herbs:
            print(f"  [{term}] no herb row")
            continue
        h = herbs[0]
        rows = cur.execute(
            "SELECT c.ingredient_id, c.name_en, c.formula, c.pubchem_id, "
            "COALESCE(c.isomeric_smiles, c.smiles) AS smi "
            "FROM herb_compound hc JOIN compounds c ON c.ingredient_id = hc.ingredient_id "
            "WHERE hc.herb_id = ? LIMIT 12",
            (h["herb_id"],),
        ).fetchall()
        print(f"  [{term}] herb_id={h['herb_id']} {h['name_cn']} -> {len(rows)} compound(s)")
        for r in rows:
            print(f"    id={r['ingredient_id']} name={r['name_en']!r} formula={r['formula']} "
                  f"pubchem={r['pubchem_id']} smiles={(r['smi'] or '')[:90]}")

    con.close()


if __name__ == "__main__":
    main()
