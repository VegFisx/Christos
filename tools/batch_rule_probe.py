# -*- coding: utf-8 -*-
"""Batch-probe candidate reaction templates against standard and held-out cases.

This tool only *evaluates* candidates.  It never edits rules.json.  A manifest
entry supplies a SMARTS, standard cases, external case IDs, and optional
byproducts/co-reagents for an approximate formula balance check.

Usage:
    D:\\TCMAI\\venv\\Scripts\\python.exe -I -X utf8 tools\\batch_rule_probe.py
    ... --manifest tools\\rule_candidates.json --out reports\\rule_candidate_probe.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "libs", ROOT / "core", ROOT / "tools", ROOT / "conditions"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions, rdMolDescriptors

DEFAULT_MANIFEST = ROOT / "tools" / "rule_candidates_20261124.json"
DEFAULT_HOLDOUT = ROOT / "data" / "holdout_general_organic_295_20261123.json"
DEFAULT_OUT = ROOT / "reports" / "rule_candidate_probe_20261124.json"


def ftext(f):
    out = Counter()
    for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", str(f or "")):
        out[el] += int(n or 1)
    return out


def fc(s):
    m = Chem.MolFromSmiles(str(s))
    return ftext(rdMolDescriptors.CalcMolFormula(m)) if m else ftext(s)


def key(s):
    m = Chem.MolFromSmiles(str(s or ""))
    return Chem.MolToInchiKey(m)[:14] if m else ""


def balanced(reactants, product, byproducts=None, co_reagents=None):
    if not byproducts and not co_reagents:
        return None  # no balance claim
    left = Counter()
    co = co_reagents or {}
    for s in list(reactants) + list(co.keys()):
        mult = int(co.get(s, 1))
        for k, v in fc(s).items():
            left[k] += v * mult
    right = fc(product)
    for s, n in (byproducts or {}).items():
        for k, v in ftext(s).items():
            right[k] += v * int(n)
    # normalise multiplicities for co-reagents
    return all(abs(left.get(k, 0) - right.get(k, 0)) < 1e-6
               for k in set(left) | set(right))


def run_candidate(cand, cases):
    rid = cand.get("id") or "(missing id)"
    sm = cand.get("smarts") or ""
    row = {"id": rid, "smarts": sm, "standard": [], "external": [],
           "errors": []}
    try:
        rx = rdChemReactions.ReactionFromSmarts(sm)
    except Exception as ex:
        row["errors"].append("compile: %s: %s" % (type(ex).__name__, ex))
        row["verdict"] = "FAIL"
        return row
    if rx is None:
        row["errors"].append("compile: ReactionFromSmarts returned None")
        row["verdict"] = "FAIL"
        return row
    bidirectional = bool(cand.get("bidirectional"))

    def apply(reactants, target):
        mols = [Chem.MolFromSmiles(str(s)) for s in reactants]
        if not all(mols):
            return {"ok": False, "why": "bad reactant SMILES"}
        orders = [tuple(mols)]
        if bidirectional and len(mols) > 1:
            orders.append(tuple(reversed(mols)))
        best = {"ok": False, "n_products": 0, "hit": 0, "balance": None,
                "why": "no product"}
        want = key(target)
        for order in orders:
            try:
                got = rx.RunReactants(order)
            except Exception as ex:
                best["why"] = "run: %s: %s" % (type(ex).__name__, ex)
                continue
            n = len(got)
            hits = []
            for ps in got:
                for x in ps:
                    if x is None:
                        continue
                    try:
                        smi = Chem.MolToSmiles(x)
                    except Exception:
                        continue
                    if key(smi) == want:
                        hits.append(smi)
            bal = balanced([Chem.MolToSmiles(m) for m in order], target,
                           cand.get("byproducts"), cand.get("co_reagents"))
            if hits:
                best = {"ok": True, "n_products": n, "hit": len(hits),
                        "balance": bal, "why": ""}
                if bal is not False:
                    break
        return best

    required_ok = True
    for sc in cand.get("standard") or []:
        r = apply(sc["reactants"], sc["product"])
        r.update({"name": sc.get("name", ""), "target": sc["product"]})
        row["standard"].append(r)
        required_ok &= bool(r["ok"]) and r["balance"] is not False
    for cid in cand.get("external") or []:
        c = cases.get(cid)
        if not c:
            r = {"id": cid, "ok": False, "why": "case not found"}
            row["external"].append(r)
            required_ok = False
            continue
        r = apply(c["reactants"], c["product"])
        r.update({"id": cid, "class": c.get("class"), "target": c["product"]})
        row["external"].append(r)
        required_ok &= bool(r["ok"]) and r["balance"] is not False
    row["verdict"] = "PASS" if required_ok and not row["errors"] else "FAIL"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--holdout", default=str(DEFAULT_HOLDOUT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args()
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    hold = json.loads(Path(a.holdout).read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in hold["cases"]}
    rows = [run_candidate(c, cases) for c in manifest.get("candidates") or []]
    out = {"manifest": str(Path(a.manifest).resolve()), "rows": rows,
           "summary": {"n": len(rows), "pass": sum(r["verdict"] == "PASS" for r in rows),
                       "fail": sum(r["verdict"] != "PASS" for r in rows)}}
    dst = Path(a.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("%-28s %-6s %s" % ("candidate", "verdict", "detail"))
    for r in rows:
        ext = ",".join("%s:%s" % (x.get("id", "?"), "Y" if x.get("ok") else "N")
                       for x in r["external"])
        std = ",".join("Y" if x.get("ok") else "N" for x in r["standard"])
        print("%-28s %-6s std=%s ext=%s %s"
              % (r["id"], r["verdict"], std or "-", ext or "-",
                 ("; " + "; ".join(r["errors"])) if r["errors"] else ""))
    print("summary", out["summary"], "->", dst)
    return 0 if out["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
