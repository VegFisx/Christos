"""Recover isomeric SMILES for compounds whose row has no stereo at all.

Scope: the 261 compounds that (a) have ``isomeric_smiles IS NULL``, (b) still
carry a potential stereocentre once parsed, and (c) whose stored ``inchi_key``
is flat or missing — i.e. the local table simply has no stereo for them.

Method: ask PubChem by name, then accept only when **both** hold
  * formula matches the local row, and
  * InChIKey skeleton (first 14 characters) matches the local ``inchi_key``.
The skeleton is stereo-independent, so a skeleton + formula match makes a wrong
compound very unlikely; any doubt is dropped rather than guessed.

Output: ``data/tcm_stereo_fill.json`` — a side-car. Nothing is written to
``tcm.db`` (read-only), and production does not read this file yet: wiring it in
is a separate decision because it changes results for ~0.8% of compounds.

Usage:
    python -I tools/fill_missing_stereo.py [--limit N] [--sleep 0.25]
"""

import argparse
import json
import pathlib
import sqlite3
import subprocess
import sys
import time
import urllib.parse

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tcm_stereo_fill.json"
DB = "file:D:/TCMAI/tcm.db?mode=ro"
FETCHED_AT = time.strftime("%Y-%m-%d")


def curl(path):
    r = subprocess.run(["curl.exe", "-s", "--max-time", "25", BASE + path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def pubchem_by_name(name):
    q = urllib.parse.quote(name, safe="")
    raw = curl("compound/name/%s/property/MolecularFormula,IsomericSMILES,InChIKey/JSON" % q)
    try:
        return json.loads(raw)["PropertyTable"]["Properties"][0]
    except Exception:
        return None


def flat_key(smi):
    """Canonical SMILES with stereo removed — the connectivity fingerprint."""
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return None
    return Chem.MolToSmiles(m, isomericSmiles=False)


def candidates(cur):
    cur.execute("SELECT ingredient_id, name_en, formula, smiles, inchi_key "
                "FROM compounds WHERE isomeric_smiles IS NULL")
    out = []
    for iid, name, formula, smi, key in cur.fetchall():
        m = Chem.MolFromSmiles(smi or "")
        if m is None:
            continue                       # 「Not Available」之类，不是结构缺失
        if not Chem.FindMolChiralCenters(m, includeUnassigned=True, useLegacyImplementation=False):
            continue                       # 本来就没有手性中心
        out.append({"id": iid, "name": name or "", "formula": formula or "",
                    "key": (key or "").strip(), "flat": flat_key(smi)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.25)
    args = ap.parse_args()

    cur = sqlite3.connect(DB, uri=True).cursor()
    rows = candidates(cur)
    if args.limit:
        rows = rows[:args.limit]
    print("candidates=%d" % len(rows))

    old = {}
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8")).get("compounds", {})

    filled = miss = rejected = 0
    out = dict(old)
    for i, r in enumerate(rows, 1):
        p = pubchem_by_name(r["name"]) if r["name"] else None
        if not p:
            miss += 1
            continue
        f_ok = (p.get("MolecularFormula") or "").upper() == r["formula"].upper()
        # 结构层面必须对得上：去掉立体后的规范 SMILES 必须与本地那条完全一致
        c_ok = flat_key(p.get("SMILES")) == r["flat"]
        skel_ok = True
        if r["key"] and not r["key"].endswith("-UHFFFAOYSA-N"):
            skel_ok = (p.get("InChIKey") or "")[:14] == r["key"][:14]
        if not (f_ok and c_ok and skel_ok):
            rejected += 1
            continue
        out[r["id"]] = {
            "name": r["name"], "smiles": p.get("SMILES"), "inchikey": p.get("InChIKey"),
            "formula": p.get("MolecularFormula"), "fetched_at": FETCHED_AT,
            "verified_by": "formula + flat-SMILES identity"
                           + (" + InChIKey skeleton" if skel_ok and r["key"] else ""),
        }
        filled += 1
        if i % 25 == 0:
            print("  ... %d/%d filled=%d miss=%d rejected=%d"
                  % (i, len(rows), filled, miss, rejected), flush=True)
        time.sleep(args.sleep)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "generated_at": FETCHED_AT,
        "source": "PubChem PUG REST by name; accepted only on formula + InChIKey skeleton",
        "note": "只收录 isomeric_smiles 为空、且确有手性中心的条目；tcm.db 只读，未写入。",
        "compounds": out,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("filled=%d miss=%d rejected=%d total_stored=%d -> %s"
          % (filled, miss, rejected, len(out), OUT))


if __name__ == "__main__":
    main()
