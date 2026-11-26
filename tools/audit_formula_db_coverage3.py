# -*- coding: utf-8 -*-
r"""Formula coverage with the user's own synonym resources (read-only).

Resolution tiers, first hit wins:
  1 exact      name/alias in tcm.db
  2 variant    dose/processing/form normalization (see coverage2)
  3 alias_map  D:\TCMAI\data\herb_aliases_map.json  (alias -> canonical)
  4 synonymy   D:\TCMAI\data\ChineseDrugEthnonymsSynonymyTable.xlsx
               (undirected primary <-> alternate graph, depth <= 2)

Tiers 3/4 only count when the final name is a tcm.db name/alias, so no
resolution floats outside the herb database.

Read-only: all D:\TCMAI files are opened read-only; tcm.db uses mode=ro.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FORMULA = Path(r"D:\TCMAI\data\formula_db.csv")
TCM = Path(r"D:\TCMAI\tcm.db")
ALIAS_MAP = Path(r"D:\TCMAI\data\herb_aliases_map.json")
SYN_XLSX = Path(r"D:\TCMAI\data\ChineseDrugEthnonymsSynonymyTable.xlsx")
SOURCED = Path(__file__).resolve().parent.parent / "data" / "name_synonyms_sourced_20261124.json"
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\formula_db_coverage3_20261124.json")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_formula_db_coverage2 import (  # noqa: E402
    SPLIT, JUNK, clean, variants, is_chem, CN_TAIL, PRIVATE, PROC, FORM)

CHEM_TAIL = ("酸镁", "酸钠", "酸钾", "酸钙", "酸锌", "硬脂酸", "糊精", "淀粉",
             "纤维素", "甘油", "乙醇", "糖浆", "色素", "香精")


def load_names():
    """Return (primary, alias_canon).

    primary     = tcm.db name_cn values (a hit is always unambiguous);
    alias_canon = alias -> set of owning name_cn (may be ambiguous).
    Aliases that are themselves primary names are dropped from alias_canon.
    """
    con = sqlite3.connect(f"file:{TCM}?mode=ro", uri=True)
    primary = set()
    alias_canon = defaultdict(set)
    rows = list(con.execute(
        "SELECT name_cn, alias FROM herbs WHERE name_cn IS NOT NULL"))
    for name_cn, _alias in rows:
        n = str(name_cn).strip()
        if n:
            primary.add(n)
    for name_cn, alias in rows:
        n = str(name_cn).strip()
        if not n:
            continue
        for x in re.split(r"[,，、;；/|]+", str(alias or "")):
            x = x.strip()
            if x:
                alias_canon[x].add(n)
    for a in [a for a in alias_canon if a in primary]:
        del alias_canon[a]
    con.close()
    return primary, alias_canon


def load_synonyms():
    import openpyxl
    wb = openpyxl.load_workbook(SYN_XLSX, read_only=True)
    ws = wb["1-to-1 records"]
    graph = defaultdict(set)
    for row in ws.iter_rows(min_row=2, values_only=True):
        p, a = row[1], row[3]
        if not p or not a:
            continue
        p, a = str(p).strip(), str(a).strip()
        if p and a and p != a:
            graph[p].add(a)
            graph[a].add(p)
    wb.close()
    return graph


def canon_of(x, primary, alias_canon):
    if x in primary:
        return {x}
    return set(alias_canon.get(x) or ())


def synonym_canon(token, graph, primary, alias_canon, depth=2):
    """All tcm.db canonical herbs reachable through the synonym graph."""
    seen = {token}
    frontier = [token]
    found = set()
    for _ in range(depth):
        nxt = []
        for x in frontier:
            for y in graph.get(x, ()):
                if y in seen:
                    continue
                seen.add(y)
                found |= canon_of(y, primary, alias_canon)
                nxt.append(y)
        frontier = nxt
        if not frontier:
            break
    return found


def soft_keys(token):
    """Conservative lookup keys: the cleaned token and its dose-stripped form.

    Processing-prefix stripping is NOT used here: 炙草 -> 草 -> alias-map ->
    a different herb is a real false positive seen in testing.
    """
    keys = [token]
    t = CN_TAIL.sub("", PRIVATE.sub("", token))
    if t and t != token and len(t) >= 2:
        keys.append(t)
    return keys


def _one(c):
    return (next(iter(c)), True) if len(c) == 1 else (None, False)


PART_SUFFIX = ("身", "尾", "头", "梢", "须")


def abbrev_or_part(token, primary):
    """Resolve only unambiguous abbreviations / part names.

    abbrev: 炙草 -> 炙甘草  (processing prefix + last character, unique in DB)
    part:   当归身 -> 当归, 归尾 -> 当归 (part suffix; unique in DB)
    """
    if len(token) < 2:
        return None
    # part: token = herb + part suffix, or an abbreviated herb + part suffix
    if token[-1] in PART_SUFFIX:
        base = token[:-1]
        if base in primary:
            return base, "part"
        cand = {n for n in primary if base and n.endswith(base)}
        if len(cand) == 1:
            return next(iter(cand)), "part"
    # abbrev: prefix + single character, unique full name in DB
    for p in PROC:
        if token.startswith(p) and len(token) == len(p) + 1:
            tail = token[-1]
            cand = {n for n in primary
                    if n.startswith(p) and n.endswith(tail) and len(n) > 2}
            if len(cand) == 1:
                return next(iter(cand)), "abbrev"
    return None


def resolve(token, primary, alias_canon, alias_map, graph, allow_parts=True,
            sourced=None):
    """Resolve only when the target herb is unambiguous.

    A synonym cluster that touches two different tcm.db herbs is reported as
    `ambiguous` instead of picking one arbitrarily.  Testing showed arbitrary
    picks are wrong often enough to poison a coverage number (e.g.
    麦门冬 -> 虋冬, 芙蓉叶 -> 木棉).
    """
    if token in primary:
        return token, "exact"
    if token in alias_canon:
        got, ok = _one(alias_canon[token])
        return (got, "exact") if ok else (None, "ambiguous")
    for v in variants(token):
        # a one-character residue is never a safe herb name
        if len(v) < 2:
            continue
        if v in primary:
            return v, "variant"
        if v in alias_canon:
            got, ok = _one(alias_canon[v])
            return (got, "variant") if ok else (None, "ambiguous")
    if allow_parts:
        got = abbrev_or_part(token, primary)
        if got:
            return got
    if sourced:
        for k in soft_keys(token):
            c = sourced.get(k)
            if c and c in primary:
                return c, "sourced_synonym"
    for k in soft_keys(token):
        m = alias_map.get(k)
        if not m:
            continue
        c = canon_of(m, primary, alias_canon)
        if not c:
            for vv in variants(m):
                if len(vv) >= 2:
                    c = canon_of(vv, primary, alias_canon)
                    if c:
                        break
        if c:
            got, ok = _one(c)
            return (got, "alias_map") if ok else (None, "ambiguous")
    for k in soft_keys(token):
        c = synonym_canon(k, graph, primary, alias_canon)
        if c:
            got, ok = _one(c)
            return (got, "synonymy") if ok else (None, "ambiguous")
    return None, "unresolved"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-alias-map", action="store_true",
                    help="use only the sourced synonymy table (no auto-built alias map)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--keep-tiers", action="store_true",
                    help="store the per-mention tier list (large; for debugging)")
    ap.add_argument("--no-parts", action="store_true",
                    help="do not resolve abbreviations/part names (炙草/归尾)")
    args = ap.parse_args()
    primary, alias_canon = load_names()
    alias_map = {} if args.no_alias_map else json.loads(
        ALIAS_MAP.read_text(encoding="utf-8"))
    graph = load_synonyms()
    sourced = {}
    if SOURCED.exists():
        for e in json.loads(SOURCED.read_text(encoding="utf-8")).get("entries") or []:
            if e.get("alias") and e.get("canonical"):
                sourced[e["alias"].strip()] = e["canonical"].strip()
    print("tcm primary", len(primary), "aliases", len(alias_canon),
          "alias_map", len(alias_map), "synonym graph nodes", len(graph),
          "sourced entries", len(sourced))

    rows = []
    tiers = Counter()
    with FORMULA.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            formula = (r.get("配方") or "").strip()
            herbs = []
            for x in SPLIT.split(formula):
                x = clean(x)
                if x and x not in ("适量", "各适量", "等份", "适量。", "少许") \
                        and x not in JUNK:
                    herbs.append(x)
            if not herbs:
                continue
            resolved, unresolved, ambiguous, chem = [], [], [], []
            for h in herbs:
                got, tier = resolve(h, primary, alias_canon, alias_map, graph,
                                    allow_parts=not args.no_parts,
                                    sourced=sourced)
                if got:
                    resolved.append((h, got, tier))
                    tiers[tier] += 1
                elif tier == "ambiguous":
                    ambiguous.append(h)
                    tiers["ambiguous"] += 1
                else:
                    unresolved.append(h)
                    if is_chem(h):
                        chem.append(h)
            row = {"formula": r.get("方名") or "",
                   "n_ingredients": len(herbs),
                   "n_resolved": len(resolved),
                   "n_ambiguous": len(ambiguous),
                   "n_unresolved": len(unresolved),
                   "n_chem": len(chem),
                   "unresolved": unresolved,
                   "ambiguous": ambiguous}
            if args.keep_tiers:
                row["resolved_tiers"] = resolved
            rows.append(row)

    n = len(rows)
    total = sum(x["n_ingredients"] for x in rows)
    res = sum(x["n_resolved"] for x in rows)
    chem = sum(x["n_chem"] for x in rows)
    ambiguous = sum(x["n_ambiguous"] for x in rows)
    full = sum(1 for x in rows
               if x["n_unresolved"] == 0 and x["n_ambiguous"] == 0)
    full_no_chem = sum(1 for x in rows
                       if x["n_unresolved"] - x["n_chem"] == 0
                       and x["n_ambiguous"] == 0)
    unresolved = Counter(h for x in rows for h in x["unresolved"]
                         if not is_chem(h))
    ambig = Counter(h for x in rows for h in x["ambiguous"])
    summary = {
        "formula_rows": n,
        "ingredient_mentions": total,
        "resolved": res,
        "resolved_pct": round(100.0 * res / total, 2) if total else 0,
        "resolved_pct_herb_like": round(100.0 * res / (total - chem), 2)
        if total > chem else 0,
        "tiers": dict(tiers),
        "ambiguous_mentions": ambiguous,
        "top_ambiguous": ambig.most_common(10),
        "chem_like_unresolved": chem,
        "formulas_all_resolved_pct": round(100.0 * full / n, 2) if n else 0,
        "formulas_all_resolved_pct_herb_like":
            round(100.0 * full_no_chem / n, 2) if n else 0,
        "top_unresolved_herb_like": unresolved.most_common(20),
    }
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows},
                                         ensure_ascii=False, indent=1),
                              encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
