# -*- coding: utf-8 -*-
r"""End-to-end audit: formula -> herbs -> compounds -> engine -> products.

Samples formulas from the user's formula library (read-only), resolves herb
names with the same resolver as coverage3, pulls components from tcm.db
(preferring isomeric_smiles, matching the production path), runs one decoction
round, and reports coverage / products / rule hits / failures / seconds.

This is an integration audit, not a correctness benchmark.

Usage:
  python tools\audit_formula_end2end.py --n 20
  python tools\audit_formula_end2end.py --formula 四逆汤
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "tools", ROOT / "core", ROOT / "conditions"):
    sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

import audit_formula_db_coverage3 as C3  # noqa: E402
import validate_formula_decoction as F  # noqa: E402

FORMULA = Path(r"D:\TCMAI\data\formula_db.csv")
TCM = Path(r"D:\TCMAI\tcm.db")
OUT_JSON = ROOT / "reports" / "formula_end2end_20261125.json"
OUT_MD = ROOT / "reports" / "formula_end2end_20261125.md"


def canon_key(smi: str) -> str:
    m = Chem.MolFromSmiles(smi or "")
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def load_components(con, herb_id: str, limit: int):
    """Components with structure; isomeric_smiles first (production path)."""
    rows = con.execute(
        "SELECT c.ingredient_id, c.name_en, c.isomeric_smiles, c.smiles, c.formula "
        "FROM herb_compound hc JOIN compounds c ON c.ingredient_id=hc.ingredient_id "
        "WHERE hc.herb_id=?", (herb_id,)).fetchall()
    out, seen = [], set()
    for iid, name, iso, smi, formula in rows:
        s = (iso or "").strip() or (smi or "").strip()
        if not s:
            continue
        key = canon_key(s)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"id": iid, "name": name or iid, "smiles": s,
                    "formula": formula, "key": key})
        if len(out) >= limit:
            break
    return out, len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--formula", default="", help="run one formula by exact name")
    ap.add_argument("--n", type=int, default=20, help="sample size")
    ap.add_argument("--per-herb", type=int, default=3,
                    help="max components per herb")
    ap.add_argument("--max-seeds", type=int, default=18)
    ap.add_argument("--max-pairs", type=int, default=80)
    ap.add_argument("--max-products", type=int, default=32)
    ap.add_argument("--cond", default="煎煮")
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    args = ap.parse_args()

    primary, alias_canon = C3.load_names()
    alias_map = json.loads(C3.ALIAS_MAP.read_text(encoding="utf-8"))
    graph = C3.load_synonyms()
    sourced = {}
    if C3.SOURCED.exists():
        for e in json.loads(C3.SOURCED.read_text(encoding="utf-8"))["entries"]:
            sourced[e["alias"].strip()] = e["canonical"].strip()

    con = F.db()
    rows = []
    with FORMULA.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    if args.formula:
        rows = [r for r in rows if (r.get("方名") or "").strip() == args.formula]
        if not rows:
            print("formula not found:", args.formula)
            return 2
    else:
        stride = max(1, len(rows) // max(1, args.n))
        rows = [r for i, r in enumerate(rows) if i % stride == 0][:args.n]
    print("formulas", len(rows))

    results = []
    t_all = time.time()
    used_names = Counter()
    for idx, r in enumerate(rows, 1):
        fname = (r.get("方名") or "").strip()
        formula = (r.get("配方") or "").strip()
        tokens = []
        for x in C3.SPLIT.split(formula):
            x = C3.clean(x)
            if x and x not in C3.JUNK and x not in ("适量", "各适量", "等份", "少许"):
                tokens.append(x)
        herbs, unresolved = [], []
        for t in tokens:
            got, tier = C3.resolve(t, primary, alias_canon, alias_map, graph,
                                   allow_parts=True, sourced=sourced)
            if got:
                herbs.append({"token": t, "name": got, "tier": tier})
                used_names[got] += 1
            else:
                unresolved.append(t)
        # de-duplicate herbs by canonical name
        uniq = {}
        for h in herbs:
            uniq.setdefault(h["name"], h)
        seeds, avail, missing_ids = [], 0, []
        for name, h in uniq.items():
            row = con.execute(
                "SELECT herb_id FROM herbs WHERE name_cn=?", (name,)).fetchone()
            if not row:
                missing_ids.append(name)
                continue
            comps, n_all = load_components(con, row[0], args.per_herb)
            avail += n_all
            for c in comps:
                if len(seeds) >= args.max_seeds:
                    break
                seeds.append({"name": c["name"], "smiles": c["smiles"],
                              "herb": name, "id": c["id"]})
        rec = {
            "formula": fname,
            "source": r.get("出处") or "",
            "tokens": len(tokens),
            "herbs_resolved": len(uniq),
            "herbs_unresolved": unresolved,
            "herbs_missing_id": missing_ids,
            "compounds_available": avail,
            "seeds_used": len(seeds),
            "n_products": 0,
            "n_hops": 0,
            "seconds": 0.0,
            "rules": {},
            "error": "",
        }
        if seeds:
            try:
                hops, secs = F.run_batch(seeds, args.cond,
                                         max_pairs=args.max_pairs,
                                         rounds=1,
                                         max_products_per_pair=args.max_products)
                keys = set()
                rc = Counter()
                for h in hops:
                    rc[h.rule or ""] += 1
                    for frag in [h.product] + (h.co_products or "").split("|"):
                        k = canon_key(frag)
                        if k:
                            keys.add(k)
                rec.update({"n_products": len(keys), "n_hops": len(hops),
                            "seconds": secs, "rules": dict(rc.most_common(10))})
            except Exception as exc:
                rec["error"] = "%s %s" % (type(exc).__name__, exc)
        results.append(rec)
        print("  %d/%d %s herbs=%d seeds=%d products=%d %.1fs%s"
              % (idx, len(rows), fname[:18], rec["herbs_resolved"],
                 rec["seeds_used"], rec["n_products"], rec["seconds"],
                 (" ERR " + rec["error"]) if rec["error"] else ""), flush=True)
    con.close()

    n = len(results)
    ran = [x for x in results if x["seeds_used"] > 0 and not x["error"]]
    prods = sorted(x["n_products"] for x in ran)
    summary = {
        "formulas": n,
        "with_herbs_resolved": sum(1 for x in results if x["herbs_resolved"] > 0),
        "with_engine_run": len(ran),
        "errors": sum(1 for x in results if x["error"]),
        "median_products": prods[len(prods) // 2] if prods else 0,
        "min_products": prods[0] if prods else 0,
        "max_products": prods[-1] if prods else 0,
        "median_seconds": (sorted(x["seconds"] for x in ran)[len(ran) // 2]
                           if ran else 0),
        "total_seconds": round(time.time() - t_all, 1),
        "top_unresolved_herbs": Counter(
            t for x in results for t in x["herbs_unresolved"]).most_common(20),
        "top_rules": Counter(
            r for x in results for r in x["rules"]).most_common(15),
        "params": vars(args),
    }
    out = {"summary": summary, "rows": results}
    Path(args.out_json).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    lines = ["# Formula end-to-end audit", "",
             "- formulas: %d" % n,
             "- with >=1 herb resolved: %d" % summary["with_herbs_resolved"],
             "- engine ran: %d" % summary["with_engine_run"],
             "- errors: %d" % summary["errors"],
             "- products (median/min/max): %d / %d / %d"
             % (summary["median_products"], summary["min_products"],
                summary["max_products"]),
             "- median seconds/formula: %.1f" % summary["median_seconds"],
             "- total seconds: %.0f" % summary["total_seconds"], "",
             "| formula | herbs | unresolved | compounds avail | seeds | products | sec |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for x in results:
        lines.append("| %s | %d | %d | %d | %d | %d | %.1f |" %
                     (x["formula"], x["herbs_resolved"], len(x["herbs_unresolved"]),
                      x["compounds_available"], x["seeds_used"],
                      x["n_products"], x["seconds"]))
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("params",)}, ensure_ascii=False, indent=1))
    print("written", args.out_json, args.out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
