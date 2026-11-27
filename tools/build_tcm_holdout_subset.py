# -*- coding: utf-8 -*-
"""Build a tiny tcm.db subset containing every seed/target used by the paozhi holdout.

The full tcm.db is not distributed with the public repository.  This script
extracts only the compounds referenced by the frozen holdout files (and the
matching herb links) into ``data/tcm_holdout.db``.  It never writes to the
source database.

Usage:
    python -I tools/build_tcm_holdout_subset.py [--source D:/TCMAI/tcm.db]
                                               [--out data/tcm_holdout.db]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
HOLDOUTS = [
    ROOT / "data" / "holdout_paozhi.json",
    ROOT / "data" / "holdout_paozhi_multiround.json",
    ROOT / "data" / "holdout_paozhi_structure_supplement_20261127.json",
]


def collect_ids() -> tuple[set[str], int]:
    ids: set[str] = set()
    n_cases = 0
    for p in HOLDOUTS:
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for case in d.get("cases") or []:
            n_cases += 1
            seed = case.get("seed") or {}
            if seed.get("iid"):
                ids.add(str(seed["iid"]))
            for t in case.get("targets") or []:
                val = str(t.get("value") or "")
                if t.get("kind") == "key" and val.startswith("HBIN"):
                    ids.add(val)
    return ids, n_cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=r"D:/TCMAI/tcm.db")
    ap.add_argument("--out", default=str(ROOT / "data" / "tcm_holdout.db"))
    a = ap.parse_args()
    src_path = Path(a.source)
    out_path = Path(a.out)
    if not src_path.exists():
        print("source not found:", src_path)
        return 2
    ids, n_cases = collect_ids()
    if not ids:
        print("no holdout ids found")
        return 2
    if out_path.exists():
        out_path.unlink()

    src = sqlite3.connect("file:" + src_path.as_posix() + "?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(out_path)
    for table in ("herbs", "compounds", "herb_compound"):
        row = src.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        if row is None:
            print("source missing table:", table)
            return 2
        dst.execute(row["sql"])

    q = ",".join("?" * len(ids))
    comp_rows = src.execute(
        "SELECT * FROM compounds WHERE ingredient_id IN (%s)" % q,
        tuple(sorted(ids))).fetchall()
    comp_cols = [d[1] for d in src.execute("PRAGMA table_info(compounds)")]
    dst.executemany(
        "INSERT INTO compounds (%s) VALUES (%s)"
        % (",".join(comp_cols), ",".join("?" * len(comp_cols))),
        [tuple(r[c] for c in comp_cols) for r in comp_rows])

    hc_rows = src.execute(
        "SELECT * FROM herb_compound WHERE ingredient_id IN (%s)" % q,
        tuple(sorted(ids))).fetchall()
    hc_cols = [d[1] for d in src.execute("PRAGMA table_info(herb_compound)")]
    dst.executemany(
        "INSERT INTO herb_compound (%s) VALUES (%s)"
        % (",".join(hc_cols), ",".join("?" * len(hc_cols))),
        [tuple(r[c] for c in hc_cols) for r in hc_rows])

    herb_ids = sorted({r["herb_id"] for r in hc_rows})
    if herb_ids:
        hq = ",".join("?" * len(herb_ids))
        h_rows = src.execute(
            "SELECT * FROM herbs WHERE herb_id IN (%s)" % hq, tuple(herb_ids)).fetchall()
        h_cols = [d[1] for d in src.execute("PRAGMA table_info(herbs)")]
        dst.executemany(
            "INSERT INTO herbs (%s) VALUES (%s)"
            % (",".join(h_cols), ",".join("?" * len(h_cols))),
            [tuple(r[c] for c in h_cols) for r in h_rows])
    else:
        h_rows = []

    dst.execute("CREATE TABLE _meta (key TEXT PRIMARY KEY, value TEXT)")
    dst.executemany("INSERT INTO _meta VALUES (?,?)", [
        ("source", str(src_path)),
        ("built_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ("holdout_cases", str(n_cases)),
        ("requested_ids", str(len(ids))),
        ("compounds_copied", str(len(comp_rows))),
        ("herbs_copied", str(len(h_rows))),
        ("note", "holdout-only subset; not a substitute for the full tcm.db"),
    ])
    dst.commit()
    src.close()
    dst.close()
    print("wrote", out_path)
    print("requested ids", len(ids), "compounds", len(comp_rows),
          "herb links", len(hc_rows), "herbs", len(h_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
