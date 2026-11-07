# -*- coding: utf-8 -*-
"""Look up compounds for 桂枝汤 / 麻黄汤 validation (read-only on tcm.db)."""
import sys, sqlite3
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB = "file:D:/TCMAI/tcm.db?mode=ro"
NAMES = [
    "Cinnamaldehyde", "Cinnamic acid", "Cinnamyl alcohol", "Coumarin",
    "Paeoniflorin", "Paeonol", "Paeoniflorigenone",
    "Glycyrrhizin", "Glycyrrhetinic acid", "Liquiritin", "Liquiritigenin",
    "6-Gingerol", "Gingerol",
    "Ephedrine", "Pseudoephedrine", "Norephedrine", "Methylephedrine",
    "Amygdalin", "Prunasin", "Mandelonitrile", "Benzaldehyde", "Benzoic acid",
    "Jujuboside A", "Jujuboside B", "Spinosin",
]

con = sqlite3.connect(DB, uri=True)
cur = con.cursor()
for n in NAMES:
    rows = cur.execute(
        "SELECT ingredient_id,name_en,formula,smiles,inchi_key FROM compounds "
        "WHERE lower(name_en)=lower(?)", (n,)).fetchall()
    if not rows:
        rows = cur.execute(
            "SELECT ingredient_id,name_en,formula,smiles,inchi_key FROM compounds "
            "WHERE lower(name_en) LIKE lower(?) LIMIT 3", (n + "%",)).fetchall()
    if not rows:
        print(f"- {n}: NOT FOUND")
        continue
    for r in rows:
        print(f"- {n}: {r[0]}|{r[1]}|{r[2]}|{(r[3] or '')[:60]}|{(r[4] or '')[:14]}")

print("\n== herbs ==")
for h in ("桂枝", "芍药", "白芍", "赤芍", "甘草", "生姜", "大枣", "麻黄", "杏仁", "苦杏仁"):
    rows = cur.execute(
        "SELECT herb_id,name_cn,latin FROM herbs WHERE name_cn=?", (h,)).fetchall()
    if not rows:
        rows = cur.execute(
            "SELECT herb_id,name_cn,latin FROM herbs WHERE name_cn LIKE ? LIMIT 2",
            (h + "%",)).fetchall()
    print(f"- {h}: " + (", ".join(f"{a}|{b}" for a, b, c in rows) if rows else "NOT FOUND"))
    for hid, _n, _l in rows:
        cnt = cur.execute("SELECT COUNT(*) FROM herb_compound WHERE herb_id=?", (hid,)).fetchone()[0]
        print(f"    {hid} compounds={cnt}")
con.close()
