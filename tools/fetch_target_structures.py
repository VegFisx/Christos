"""Fetch target structures for the paozhi validation from PubChem.

Why this file exists
--------------------
Three paozhi cases could only be compared at formula level because the local
``tcm.db`` has no entry for the literature target. Two of them stay at that
level: PubChem has no entry named ``2,3,5,4'-tetrahydroxystilbene`` (the THSG
aglycone) or for the ring-opened acid of jolkinolide B, so there is no structure
to compare against and inventing one is not allowed.

The atractyloside case does resolve. The literature target is the decarboxylation
product of carboxyatractyloside, i.e. atractylosidic acid, C30H46O16S2. PubChem
carries four entries on that skeleton (CID 442005 named ``Atractylosidic acid``
plus three stereoisomers); we store all four so the comparison can say whether a
product matches the named compound, the skeleton only, or neither.

Every record carries cid, smiles, inchikey, formula, title, url and fetched_at,
so a reader can re-fetch and check. Nothing here is hand-written.

Usage
-----
    python -I tools/fetch_target_structures.py
"""

import json
import pathlib
import subprocess
import sys
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/"
OUT = pathlib.Path(__file__).resolve().parent.parent / "data" / "target_structures.json"
FETCHED_AT = "2026-11-07"

TARGETS = [
    # label, cid, why it is here
    ("atractylosidic_acid", 442005, "文献目标：苍耳子砂炒脱羧产物（ATR 骨架）"),
    ("atractylosidic_acid_iso_a", 23619477, "同一骨架的立体异构条目"),
    ("atractylosidic_acid_iso_b", 6325952, "同一骨架的立体异构条目"),
    ("atractylosidic_acid_flat", 2255, "同一骨架、无立体信息的条目"),
]

UNAVAILABLE = [
    ("THSG 苷元", "2,3,5,4'-tetrahydroxystilbene",
     "PubChem 无该名称条目（5281717 是 2,3',4,5'- 异构体，不是苷元）"),
    ("JNB 开环酸", "jolkinolide B ring-opened acid",
     "PubChem 只有 jolkinolide B 本体（CID 161954），无开环酸条目"),
]


def curl_get(path):
    url = BASE + path
    res = subprocess.run(
        ["curl.exe", "-s", "--max-time", "30", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return res.stdout


def fetch_props(cid):
    props = "MolecularFormula,InChIKey,IsomericSMILES,Title"
    raw = curl_get("compound/cid/%d/property/%s/JSON" % (cid, props))
    try:
        obj = json.loads(raw)
        return obj["PropertyTable"]["Properties"][0]
    except Exception:
        raise SystemExit("PubChem lookup failed for CID %d: %s" % (cid, raw[:200]))


def main():
    compounds = {}
    for label, cid, why in TARGETS:
        p = fetch_props(cid)
        compounds[label] = {
            "cid": cid,
            "title": p.get("Title"),
            "formula": p.get("MolecularFormula"),
            "smiles": p.get("SMILES"),
            "inchikey": p.get("InChIKey"),
            "skeleton_prefix": (p.get("InChIKey") or "")[:14],
            "url": "https://pubchem.ncbi.nlm.nih.gov/compound/%d" % cid,
            "fetched_at": FETCHED_AT,
            "why": why,
        }
        print("%-26s CID %-9d %-14s %s" % (label, cid, p.get("MolecularFormula"), p.get("Title")))

    doc = {
        "generated_at": FETCHED_AT,
        "source": "PubChem PUG REST (compound/cid/<id>/property)",
        "note": "只收录能从 PubChem 按 CID 取到的结构；取不到的一律记在 unavailable，不手写。",
        "compounds": compounds,
        "unavailable": [{"label": l, "query": q, "reason": r} for l, q, r in UNAVAILABLE],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote %s (%d compounds, %d unavailable)" % (OUT, len(compounds), len(UNAVAILABLE)))


if __name__ == "__main__":
    main()
