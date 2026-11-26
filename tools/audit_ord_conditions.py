# -*- coding: utf-8 -*-
r"""For rules with ORD product matches, tabulate the conditions of those matches.

Question: for a rule that reproduced a recorded ORD product, how often did the
record use water as a solvent and a temperature <= 100 C?  This is evidence
about plausibility of the transformation in aqueous/mild settings, NOT a gate.

Reuses the rule/template machinery of audit_rules_against_ord_reactions.py.
Read-only.

Usage:
  python tools\audit_ord_conditions.py --limit 120000            # active secondary
  python tools\audit_ord_conditions.py --only id1,id2 --limit 120000
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from itertools import product
from pathlib import Path

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from audit_rules_against_ord_reactions import (  # noqa: E402
    INDEX_PATH, canons_of, count_lines, load_rules, build_rule_objs)

OUT_JSON = ROOT / "reports" / "ord_conditions_20261124.json"
OUT_MD = ROOT / "reports" / "ord_conditions_20261124.md"

NUM = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s+(\d+)\s*$")
WATER = {"water", "h2o", "d2o", "water-d2", "distilled water", "deionized water"}

# transition metals + common Lewis-acid metals; alkali/alkaline earth are left
# out because Na/K/Ca salts are usually bases/buffers, not catalysts.
METAL_SYM = ("Pd|Pt|Cu|Ni|Co|Fe|Ru|Rh|Ir|Ag|Au|Zn|Mn|Cr|Mo|W|Ti|Zr|Hf|V|Nb|"
             "Ta|Sn|Al|In|Ga|Bi|Sb|Pb|Hg|Cd|La|Ce|Pr|Nd|Sm|Eu|Gd|Tb|Dy|Ho|"
             "Er|Tm|Yb|Lu|Sc|Y")
METAL_NAME = ("palladium|platinum|copper|nickel|cobalt|iron|ruthenium|rhodium|"
              "iridium|silver|gold|zinc|manganese|chromium|molybdenum|tungsten|"
              "titanium|zirconium|hafnium|vanadium|niobium|tantalum|tin|"
              "aluminum|aluminium|indium|gallium|bismuth|antimony|lead|mercury|"
              "cadmium|lanthanum|cerium|samarium|europium|ytterbium|scandium|yttrium")
METAL_RE = re.compile(r"(?:^|[^A-Za-z])(?:%s)(?:[^a-z]|$)|\\b(?:%s)\\b"
                      % (METAL_SYM, METAL_NAME), re.I)


def parse_temp(s: str):
    """Return (value_C, flag) or (None, None). ORD stores '<value> <flag>'."""
    m = NUM.match(str(s or ""))
    if not m:
        return None, None
    return float(m.group(1)), int(m.group(2))


def is_water(sols):
    return any(str(s).strip().lower() in WATER for s in sols or [])


def is_water_only(sols):
    lo = [str(s).strip().lower() for s in sols or [] if str(s).strip()]
    return bool(lo) and all(s in WATER for s in lo)


def has_metal(catalysts, reagents):
    txt = " ".join(str(x) for x in (catalysts or []) + (reagents or []))
    return bool(METAL_RE.search(txt))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=120000)
    ap.add_argument("--only", default="",
                    help="rule ids; default = active secondary rules")
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    args = ap.parse_args()

    rules = load_rules()
    if args.only:
        keep = {x.strip() for x in args.only.split(",") if x.strip()}
        rules = [r for r in rules if r.get("id") in keep]
    else:
        rules = [r for r in rules
                 if str(r.get("status") or "active") == "active"
                 and str(r.get("provenance")) == "secondary"]
    robjs = build_rule_objs(rules)
    print("rules", len(rules))

    total = count_lines(INDEX_PATH)
    stride = max(1, total // max(1, args.limit))
    print("index", total, "stride", stride)

    st = {x["rule"]["id"]: {
        "match": 0, "with_cond": 0, "temp_le_100": 0, "water": 0,
        "water_temp_le_100": 0, "water_no_temp": 0,
        "le100_nometal": 0, "water_only": 0, "water_only_le100": 0,
        "water_only_le100_nometal": 0,
        "temps_water": Counter(), "solvents_water": Counter(),
    } for x in robjs}

    t0 = time.time()
    kept = 0
    with INDEX_PATH.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh):
            if lineno % stride:
                continue
            if kept >= args.limit:
                break
            kept += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            reactants = rec.get("reactants") or []
            if not reactants:
                continue
            mols = []
            ok = True
            for smi in reactants:
                m = Chem.MolFromSmiles(smi)
                if m is None:
                    ok = False
                    break
                mols.append(m)
            if not ok or not mols:
                continue
            actual = set()
            for smi in rec.get("products") or []:
                pm = Chem.MolFromSmiles(smi)
                if pm is not None:
                    actual |= canons_of(pm)
            if not actual:
                continue

            temps = rec.get("temp") or ""
            sols = rec.get("solvents") or []
            metal = has_metal(rec.get("catalysts"), rec.get("reagents"))
            val0, flag0 = parse_temp(temps)
            le100 = val0 is not None and flag0 == 1 and val0 <= 100
            water_only = is_water_only(sols)
            for x in robjs:
                rid = x["rule"]["id"]
                rxn = x["rxn"]
                if rxn is None:
                    continue
                hits = []
                for tpl in x["templates"]:
                    hits.append([i for i, m in enumerate(mols)
                                 if m.HasSubstructMatch(tpl)])
                if any(not h for h in hits):
                    continue
                matched = False
                for idxs in product(*hits):
                    try:
                        prods = rxn.RunReactants(tuple(mols[i] for i in idxs))
                    except Exception:
                        continue
                    for tup in prods:
                        for pmol in tup:
                            if canons_of(pmol) & actual:
                                matched = True
                                break
                        if matched:
                            break
                    if matched:
                        break
                if not matched:
                    continue
                s = st[rid]
                s["match"] += 1
                val, flag = parse_temp(temps)
                wet = bool(temps) or bool(sols)
                if wet:
                    s["with_cond"] += 1
                if val is not None and flag == 1 and val <= 100:
                    s["temp_le_100"] += 1
                if le100 and not metal:
                    s["le100_nometal"] += 1
                if water_only:
                    s["water_only"] += 1
                    if le100:
                        s["water_only_le100"] += 1
                        if not metal:
                            s["water_only_le100_nometal"] += 1
                if is_water(sols):
                    s["water"] += 1
                    for z in sols:
                        if str(z).strip().lower() in WATER:
                            s["solvents_water"][str(z)] += 1
                    if temps:
                        s["temps_water"][str(temps)] += 1
                    if val is not None and flag == 1 and val <= 100:
                        s["water_temp_le_100"] += 1
                    elif not temps:
                        s["water_no_temp"] += 1

    rows = []
    for x in robjs:
        rid = x["rule"]["id"]
        s = st[rid]
        rows.append({
            "id": rid,
            "match": s["match"],
            "with_condition": s["with_cond"],
            "temp_le_100": s["temp_le_100"],
            "water": s["water"],
            "water_temp_le_100": s["water_temp_le_100"],
            "water_no_temp": s["water_no_temp"],
            "le100_nometal": s["le100_nometal"],
            "water_only": s["water_only"],
            "water_only_le100": s["water_only_le100"],
            "water_only_le100_nometal": s["water_only_le100_nometal"],
            "top_water_temps": dict(s["temps_water"].most_common(8)),
            "top_water_solvents": dict(s["solvents_water"].most_common(8)),
        })
    rows.sort(key=lambda r: (-r["water_only_le100_nometal"],
                             -r["water_only_le100"],
                             -r["water_temp_le_100"], r["id"]))

    summary = {
        "rules": len(rows),
        "with_water": sum(1 for r in rows if r["water"] > 0),
        "with_water_and_le100": sum(1 for r in rows if r["water_temp_le_100"] > 0),
        "with_water_le100_ge3": sum(1 for r in rows if r["water_temp_le_100"] >= 3),
        "with_water_le100_ge10": sum(1 for r in rows if r["water_temp_le_100"] >= 10),
        "with_le100_nometal": sum(1 for r in rows if r["le100_nometal"] > 0),
        "with_water_only": sum(1 for r in rows if r["water_only"] > 0),
        "with_water_only_le100": sum(1 for r in rows if r["water_only_le100"] > 0),
        "with_water_only_le100_nometal":
            sum(1 for r in rows if r["water_only_le100_nometal"] > 0),
        "scanned": kept,
        "elapsed_sec": round(time.time() - t0, 1),
        "index": str(INDEX_PATH),
    }
    out = {"summary": summary, "rows": rows}
    Path(args.out_json).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    lines = ["# ORD conditions for product-match records", "",
             "- rules: %d" % len(rows),
             "- scanned records: %d" % kept,
             "- rules with water in a matching record: **%d**" % summary["with_water"],
             "- water AND temp <= 100 C: **%d**" % summary["with_water_and_le100"],
             "- at least 3 such records: %d" % summary["with_water_le100_ge3"],
             "- at least 10 such records: %d" % summary["with_water_le100_ge10"],
             "- water-only solvent AND temp <= 100 C: **%d**"
             % summary["with_water_only_le100"],
             "- water-only AND <= 100 C AND no metal catalyst: **%d**"
             % summary["with_water_only_le100_nometal"],
             "",
             "| rule | matches | <=100C no metal | water-only | water-only&<=100C "
             "| water-only&<=100C&no metal | water | water&<=100C |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        lines.append("| `%s` | %d | %d | %d | %d | %d | %d | %d |" %
                     (r["id"], r["match"], r["le100_nometal"], r["water_only"],
                      r["water_only_le100"], r["water_only_le100_nometal"],
                      r["water"], r["water_temp_le_100"]))
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print("written", args.out_json, args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
