# -*- coding: utf-8 -*-
"""Build rules/paozhi_adjuvants.json from tcm.db (read-only).

No SMILES is typed by hand: every structure is read from tcm.db by ingredient_id.
The database is opened with a read-only URI; -wal / -shm are never touched.

Usage:
  python -I tools/build_paozhi_adjuvants.py
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DB_URI = "file:D:/TCMAI/tcm.db?mode=ro"
OUT = Path("D:/ProgramData/DSHNS/chemreact-staging/rules/paozhi_adjuvants.json")

# method -> (adjuvant herb, [ingredient_id], Chinese display labels)
SPEC = {
    "蜜炙": ("HERB001711", ["HBIN028037", "HBIN026793"], {"HBIN028037": "葡萄糖", "HBIN026793": "果糖"}),
    "酒炙": ("HERB002538", ["HBIN015097"], {"HBIN015097": "乙醇"}),
    "醋炙": ("HERB000960", ["HBIN014399"], {"HBIN014399": "乙酸"}),
}


def main() -> None:
    con = sqlite3.connect(DB_URI, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    methods = {}
    for method, (herb_id, ids, labels) in SPEC.items():
        h = cur.execute(
            "SELECT herb_id, name_cn, name_en FROM herbs WHERE herb_id=?", (herb_id,)
        ).fetchone()
        if not h:
            print(f"!! {method}: herb {herb_id} not found; skipped")
            continue
        compounds = []
        for iid in ids:
            r = cur.execute(
                "SELECT ingredient_id, name_en, formula, pubchem_id, "
                "COALESCE(NULLIF(isomeric_smiles,''), smiles) AS smi "
                "FROM compounds WHERE ingredient_id=?", (iid,)
            ).fetchone()
            if not r or not r["smi"]:
                print(f"!! {method}: ingredient {iid} missing or has no SMILES; skipped")
                continue
            link = cur.execute(
                "SELECT match_level, match_source FROM herb_compound "
                "WHERE herb_id=? AND ingredient_id=?", (herb_id, iid)
            ).fetchone()
            compounds.append({
                "ingredient_id": r["ingredient_id"],
                "name_en": r["name_en"],
                "name_cn": labels.get(iid, ""),
                "formula": r["formula"],
                "pubchem_id": (str(r["pubchem_id"]).split(".")[0] if r["pubchem_id"] else ""),
                "smiles": r["smi"],
                "match_level": (link["match_level"] if link else ""),
                "match_source": (link["match_source"] if link else ""),
            })
        methods[method] = {
            "adjuvant": h["name_cn"],
            "herb_id": h["herb_id"],
            "herb_name_en": h["name_en"],
            "compounds": compounds,
        }
        print(f"{method}: {h['name_cn']} ({herb_id}) -> {len(compounds)} compound(s): "
              + ", ".join(c["name_en"] for c in compounds))
    con.close()
    doc = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "source": DB_URI,
        "note": ("辅料共底物（P2 原型）：每个结构都按 ingredient_id 从 tcm.db 只读取回，"
                 "未手写 SMILES。仅在炮制档启用；开关见 chemreact.py --no-paozhi-adjuvant。"),
        "methods": methods,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
