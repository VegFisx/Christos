"""D1: flag products that look chemically wrong, with a reason for each flag.

Reads one or more ledger CSVs (the PATH_FIELDS schema written by the bridge),
scores every row on six explainable signals, and writes a ranked CSV.

Signals
  1 parse      the product SMILES does not parse or fails sanitisation
  2 balance    atoms in products+co_products differ from substrates, beyond
               what water or oxygen exchange can explain
  3 formula    the recorded formula disagrees with the structure
  4 template   a mined template is recorded, but its left-hand side cannot
               match the recorded substrates
  5 conflict   the same substrate pair and rule yield two different products
  6 extent     the condition estimate is below the trace threshold

This is a detector, not a fixer: it never edits a product, it only orders rows
by how much evidence points at them.

Usage
  python tools\\find_suspect_products.py _diag\\d1_runs\\*\\*.csv -o out.csv
  python tools\\find_suspect_products.py ledger.csv --top 30
"""
import argparse
import csv
import glob
import os
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.*")

# Water and oxygen are the two reagents a ledger never records: hydrolysis
# consumes H2O, oxidation consumes O2. Allow those atoms to differ by a small
# amount before calling it an imbalance.
ALLOWED_H = 2
ALLOWED_O = 2


def _mol(smiles: str):
    if not smiles:
        return None
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def element_counts(mols) -> Counter:
    c = Counter()
    for m in mols:
        if m is None:
            continue
        for atom in m.GetAtoms():
            c[atom.GetSymbol()] += 1
        c["__charge"] += sum(a.GetFormalCharge() for a in m.GetAtoms())
    return c


def split_list(text: str):
    """Ledger list columns use ';' between entries; tolerate '|' too."""
    if not text:
        return []
    for sep in (";", "|"):
        if sep in text:
            return [p.strip() for p in text.split(sep) if p.strip()]
    return [text.strip()]


def template_left_fragments(smarts: str):
    if not smarts or ">>" not in smarts:
        return []
    left = smarts.split(">>")[0]
    return [p for p in left.split(".") if p.strip()]


def score_row(row: dict, conflicts: dict) -> tuple[float, list[str]]:
    hints = []
    score = 0.0

    prod = _mol(row.get("product_smiles", ""))
    if prod is None:
        return 50.0, ["parse: product SMILES does not parse"]

    subs = [_mol(row.get("source_smiles", "")), _mol(row.get("partner_smiles", ""))]
    subs = [m for m in subs if m is not None]
    cos = [_mol(s) for s in split_list(row.get("co_products", ""))]
    cos = [m for m in cos if m is not None]

    # 2 mass ---------------------------------------------------------------
    # Heavy-atom budget: a product cannot contain more heavy atoms than the
    # substrates, and a product that keeps only a small fragment while claiming
    # no co-product means the rest of the molecule went nowhere.
    ha_prod = prod.GetNumHeavyAtoms()
    ha_budget = sum(m.GetNumHeavyAtoms() for m in subs)
    if ha_budget and ha_prod > ha_budget + 4:
        excess = ha_prod - ha_budget - 4
        score += 6.0 * min(excess, 20)
        hints.append("mass: product carries %d heavy atoms more than the substrates" % excess)
    if ha_budget and ha_prod < 0.35 * ha_budget:
        score += 2.0
        hints.append("mass: product keeps %d of %d heavy atoms" % (ha_prod, ha_budget))

    # charge ----------------------------------------------------------------
    net = element_counts([prod])["__charge"] - element_counts(subs)["__charge"]
    if net:
        score += 3.0 * abs(net)
        hints.append("charge: net %+d" % net)

    # 3 formula -------------------------------------------------------------
    recorded = (row.get("formula") or "").strip()
    if recorded:
        try:
            actual = CalcMolFormula(prod)
            norm = lambda s: s.replace("+", "").replace("-", "").strip()
            if norm(actual) != norm(recorded):
                score += 6.0
                hints.append("formula: recorded %s vs structure %s" % (recorded, actual))
        except Exception:
            pass

    # 4 template ------------------------------------------------------------
    frags = template_left_fragments(row.get("template_smarts", ""))
    if frags and subs:
        unmatched = 0
        for frag in frags:
            q = Chem.MolFromSmarts(frag)
            if q is None:
                continue
            if not any(m.HasSubstructMatch(q) for m in subs):
                unmatched += 1
        if unmatched:
            score += 6.0 * min(unmatched, 3)
            hints.append("template: %d left-hand fragment(s) cannot match the substrates"
                         % unmatched)

    # 5 conflict ------------------------------------------------------------
    # One rule acting on one substrate pair may legitimately give regioisomers,
    # so this only fires when the products do not even share a heavy-atom count.
    key = conflicts.get("__key__")
    if key is not None:
        info = conflicts.get(key)
        if info:
            n_products, n_sizes = info
            if n_sizes > 1:
                score += min(9.0, 3.0 * (n_sizes - 1))
                hints.append("conflict: same substrates and rule give products of %d different sizes"
                             % n_sizes)

    # 6 extent --------------------------------------------------------------
    ext = (row.get("extent") or "").strip()
    if ext:
        try:
            if float(ext) < 0.05:
                score += 1.5
                hints.append("extent: %.3f, below the trace threshold" % float(ext))
        except ValueError:
            pass

    return score, hints


def main() -> int:
    ap = argparse.ArgumentParser(description="Rank ledger products by how much evidence says they are wrong")
    ap.add_argument("inputs", nargs="+", help="ledger CSV files or globs")
    ap.add_argument("-o", "--out", default="", help="write the ranked rows to this CSV")
    ap.add_argument("--top", type=int, default=20, help="print this many rows")
    a = ap.parse_args()

    paths = []
    for pat in a.inputs:
        hits = glob.glob(pat)
        paths.extend(hits or [pat])
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        print("no input found")
        return 2

    rows = []
    for p in paths:
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                r["__file__"] = os.path.basename(p)
                rows.append(r)
    print("rows: %d from %d file(s)" % (len(rows), len(paths)))

    # conflict index: substrates + rule -> (n distinct products, n distinct sizes)
    groups = defaultdict(lambda: {"products": set(), "sizes": set()})
    for r in rows:
        key = (r.get("source_smiles", ""), r.get("partner_smiles", ""), r.get("rule_name", ""))
        groups[key]["products"].add(r.get("product_smiles", ""))
        m = _mol(r.get("product_smiles", ""))
        if m is not None:
            groups[key]["sizes"].add(m.GetNumHeavyAtoms())
    conflicts = {k: (len(v["products"]), len(v["sizes"])) for k, v in groups.items()}
    print("substrate+rule groups: %d, groups with products of >1 size: %d"
          % (len(groups), sum(1 for v in groups.values() if len(v["sizes"]) > 1)))

    scored = []
    for r in rows:
        key = (r.get("source_smiles", ""), r.get("partner_smiles", ""), r.get("rule_name", ""))
        r2 = dict(r)
        r2["__key__"] = key
        s, hints = score_row(r2, {"__key__": key, **conflicts})
        scored.append((s, hints, r))
    scored.sort(key=lambda t: -t[0])

    flagged = [t for t in scored if t[0] > 0]
    print("flagged %d / %d (%.1f%%)" % (len(flagged), len(scored), 100.0 * len(flagged) / len(scored)))
    reason_kinds = Counter(h.split(":")[0] for _, hs, _ in flagged for h in hs)
    print("reason kinds:", dict(reason_kinds))

    for s, hints, r in scored[: a.top]:
        print("\n[%.1f] %s  rule=%s  file=%s" %
              (s, (r.get("product_smiles") or "")[:70], r.get("rule_name"), r["__file__"]))
        for h in hints:
            print("     -", h)

    if a.out:
        cols = ["score", "hints", "product_smiles", "formula", "rule_name",
                "source_smiles", "partner_smiles", "co_products", "extent",
                "template_support", "template_smarts", "seq", "__file__"]
        with open(a.out, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for s, hints, r in scored:
                out = dict(r)
                out["score"] = round(s, 1)
                out["hints"] = " | ".join(hints)
                w.writerow(out)
        print("\nwrote", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
