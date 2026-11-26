# -*- coding: utf-8 -*-
r"""Derive and screen family-level reaction templates from standard examples.

This tool does NOT edit rules/rules.json.  For each family it:
  1. maps every standard example with RXNMapper;
  2. extracts RDChiral candidate templates (both orientations);
  3. keeps candidates that hit every family standard example and no negative;
  4. counts hits on the dev set (dev is allowed for gap analysis);
  5. writes a ranked JSON/Markdown report.

Usage:
  python tools\family_template_sweep.py
  python tools\family_template_sweep.py --family n_alkylation
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT / "tools", ROOT / "core"):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions
from rdchiral.template_extractor import extract_from_reaction
from rxnmapper import RXNMapper

MANIFEST = ROOT / "data" / "family_standard_examples_20261124.json"
DEV = ROOT / "data" / "dev_general_organic_20261124.json"
OUT_JSON = ROOT / "reports" / "family_template_sweep_20261124.json"
OUT_MD = ROOT / "reports" / "family_template_sweep_20261124.md"

def canon_key(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)[:14]
    except Exception:
        return ""

def reaction_text(ex):
    rhs = ex["product"]
    for b in ex.get("byproducts") or []:
        rhs += "." + b
    return ".".join(ex["reactants"]) + ">>" + rhs

def run_hit(rx, reactants, target_key, allow_reverse=True):
    ms = [Chem.MolFromSmiles(s) for s in reactants]
    if any(m is None for m in ms):
        return False, 0
    if len(ms) != rx.GetNumReactantTemplates():
        return False, 0
    orders = [tuple(ms)]
    if allow_reverse and len(ms) == 2:
        orders.append(tuple(reversed(ms)))
    for order in orders:
        try:
            got = rx.RunReactants(order)
        except Exception:
            continue
        for ps in got or []:
            for p in ps:
                if p is not None and canon_key(Chem.MolToSmiles(p)) == target_key:
                    return True, len(got)
    return False, 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--dev", default=str(DEV))
    ap.add_argument("--family", default=None)
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    args = ap.parse_args()

    families = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["families"]
    if args.family:
        families = [f for f in families if f["name"] == args.family]
    dev = json.loads(Path(args.dev).read_text(encoding="utf-8"))["cases"]
    mapper = RXNMapper()

    results = []
    for fam in families:
        print("\n##", fam["name"], flush=True)
        candidates = []
        for ex in fam["examples"]:
            rxn = reaction_text(ex)
            try:
                mapped = mapper.get_attention_guided_atom_maps([rxn])[0].get("mapped_rxn") or ""
                lhs, rhs = mapped.split(">>", 1)
                res = extract_from_reaction(
                    {"reactants": lhs, "products": rhs, "agents": "", "_id": ex["id"]})
                tpl = (res or {}).get("reaction_smarts") or ""
            except Exception as exc:
                print(" map/extract fail", ex["id"], type(exc).__name__, exc, flush=True)
                continue
            if ">>" not in tpl:
                print(" no template", ex["id"], flush=True)
                continue
            a, b = tpl.split(">>", 1)
            for tag, sm in (("orig", tpl), ("swap", b + ">>" + a)):
                try:
                    rx = rdChemReactions.ReactionFromSmarts(sm)
                except Exception as exc:
                    print(" compile fail", ex["id"], tag, type(exc).__name__, flush=True)
                    continue
                candidates.append({"source": ex["id"], "orientation": tag,
                                   "smarts": sm, "rx": rx})

        # dedupe by SMARTS
        uniq = {}
        for c in candidates:
            uniq.setdefault(c["smarts"], c)
        candidates = list(uniq.values())

        accepted = []
        for c in candidates:
            std_pass = sum(
                1 for e in fam["examples"]
                if run_hit(c["rx"], e["reactants"], canon_key(e["product"]))[0])
            neg_ok = all(not run_hit(c["rx"], n["reactants"], canon_key(n["product"]))[0]
                         for n in fam.get("negatives") or [])
            if std_pass == 0 or not neg_ok:
                continue
            dev_hits = []
            for case in dev:
                hit, _ = run_hit(c["rx"], case["reactants"], canon_key(case["product"]))
                if hit:
                    dev_hits.append(case["id"])
            accepted.append({
                "source": c["source"],
                "orientation": c["orientation"],
                "smarts": c["smarts"],
                "standard_pass": std_pass,
                "standard_total": len(fam["examples"]),
                "negative_pass": neg_ok,
                "dev_hits": dev_hits,
                "n_dev_hits": len(dev_hits),
            })
            print(" candidate", c["source"], c["orientation"],
                  "std", std_pass, "/", len(fam["examples"]),
                  "dev_hits", len(dev_hits), flush=True)

        accepted.sort(key=lambda x: (-x["n_dev_hits"], -x["standard_pass"],
                                     len(x["smarts"])))
        results.append({"family": fam["name"], "negatives": fam.get("negatives") or [],
                        "candidates": accepted})
        print(" accepted", len(accepted), flush=True)

    out = {"manifest": str(Path(args.manifest).name), "dev": str(Path(args.dev).name),
           "families": results, "note": "Candidates only; rules.json is not edited."}
    Path(args.out_json).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Family template sweep", "",
             "Candidates are derived from standard examples and screened on dev;",
             "no rule is inserted automatically.", ""]
    for fam in results:
        lines.append("## %s" % fam["family"])
        lines.append("")
        if not fam["candidates"]:
            lines.append("No candidate passed all standard examples and negatives.")
            lines.append("")
            continue
        lines.append("| source | orientation | std pass | dev hits | SMARTS |")
        lines.append("|---|---|---:|---:|---|")
        for c in fam["candidates"]:
            lines.append("| %s | %s | %d/%d | %d | `%s` |" %
                         (c["source"], c["orientation"],
                          c["standard_pass"], c["standard_total"], c["n_dev_hits"],
                          c["smarts"].replace("|", "\\|")))
        lines.append("")
    Path(args.out_md).write_text("\n".join(lines), encoding="utf-8")
    print("\nwritten", args.out_json, args.out_md)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
