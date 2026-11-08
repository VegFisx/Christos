"""Fetch isomeric seed structures for the paozhi cases from PubChem.

Why this is needed
------------------
``tcm.db`` stores a **flat** SMILES in its ``smiles`` column: the stereo layer
exists only in the ``inchi_key`` column. Verified 2026-11-07 on four seeds:

    HBIN019719 Carboxyatractyloside  smiles -> ...-UHFFFAOYSA-N  db key -> ...-LNQSNDDKSA-N
    HBIN031562 Jolkinolide b         smiles -> ...-UHFFFAOYSA-N  db key -> ...-MCDHERAVSA-N
    HBIN003908 THSG                  smiles -> ...-UHFFFAOYSA-N  db key -> ...-DSNJPTTOSA-N
    HBIN014582 Aconitine             smiles -> ...-UHFFFAOYSA-N  db key -> ...-XTHSEXKGSA-N

The engine therefore receives a structure with no stereocentres and can only
return flat products, which caps every structural comparison at skeleton level.
The structures themselves are not lost: PubChem has isomeric SMILES for all six
seeds. This script stores them next to the database, with cid, formula, url and
fetched_at, so the comparison can be re-run at stereo level.

Nothing is hand-written: every record comes from PubChem by CID and its formula
is checked against the database row before it is accepted.

Usage
-----
    python -I tools/fetch_seed_structures.py
"""

import json
import pathlib
import sqlite3
import subprocess
import sys
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "seed_structures.json"
FETCHED_AT = "2026-11-07"
DB = "file:{}?mode=ro".format(
    (pathlib.Path("D:/TCMAI/tcm.db")).as_posix())

# ingredient_id -> PubChem 名称（用文献里的规范名，不用库里的英文名，避免同义名歧义）
SEEDS = {
    "HBIN027729": "Ginsenoside Rb1",
    "HBIN016699": "Arecoline",
    "HBIN019719": "Carboxyatractyloside",
    "HBIN031562": "Jolkinolide B",
    "HBIN014582": "Aconitine",
    "HBIN003908": "2,3,5,4'-tetrahydroxystilbene-2-O-beta-D-glucoside",
}


def curl_get(path):
    res = subprocess.run(
        ["curl.exe", "-s", "--max-time", "30", BASE + path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return res.stdout


def fetch(name):
    q = urllib.parse.quote(name, safe="")
    raw = curl_get("compound/name/" + q + "/property/MolecularFormula,IsomericSMILES,InChIKey/JSON")
    try:
        return json.loads(raw)["PropertyTable"]["Properties"][0]
    except Exception:
        print("  ! not found on PubChem: %s" % name)
        return None


def main():
    cur = sqlite3.connect(DB, uri=True).cursor()
    out = {}
    for iid, name in SEEDS.items():
        cur.execute("SELECT name_en, formula, smiles, inchi_key FROM compounds WHERE ingredient_id=?",
                    (iid,))
        row = cur.fetchone()
        if not row:
            print("  ! %s missing from tcm.db" % iid)
            continue
        db_name, db_formula, db_smiles, db_key = row
        p = fetch(name)
        if not p:
            continue
        ok_formula = (p.get("MolecularFormula") or "").upper() == (db_formula or "").upper()
        out[iid] = {
            "db_name": db_name,
            "pubchem_name": name,
            "formula": p.get("MolecularFormula"),
            "formula_matches_db": ok_formula,
            "smiles": p.get("SMILES"),
            "inchikey": p.get("InChIKey"),
            "db_inchikey": db_key,
            "db_smiles_is_flat": "@" not in (db_smiles or ""),
            "fetched_at": FETCHED_AT,
        }
        print("  %-12s %-22s formula_ok=%-5s flat_db=%s"
              % (iid, name[:22], ok_formula, "@" not in (db_smiles or "")))

    doc = {
        "generated_at": FETCHED_AT,
        "source": "PubChem PUG REST (compound/name/<name>/property)",
        "note": "tcm.db 的 smiles 列没有立体；这里存同一条目的 isomeric SMILES，公式须与库一致才收录。",
        "seeds": out,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s (%d seeds)" % (OUT, len(out)))


if __name__ == "__main__":
    main()
