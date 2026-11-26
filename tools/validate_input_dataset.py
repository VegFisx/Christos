# -*- coding: utf-8 -*-
r"""Validate a wet-lab / literature dataset against the v1 interface schema.

Format checks only: required fields, vocabularies, number parsing, InChIKey
shape, SMILES parse.  It does not judge chemical correctness.

Usage:
  python tools\validate_input_dataset.py data\my_lab.csv
  python tools\validate_input_dataset.py data\my_lab.jsonl --max-print 10
"""
from __future__ import annotations

import argparse
import csv
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
SCHEMA = ROOT / "data" / "input_dataset_schema_20261124.json"
IK = re.compile(r"^[A-Z]{14}(-[A-Z]{10}-[A-Z])?$")


def load_rows(path: Path):
    if path.suffix.lower() == ".jsonl":
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()
                if x.strip()]
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--schema", default=str(SCHEMA))
    ap.add_argument("--max-print", type=int, default=20)
    args = ap.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    req = schema["required"]
    vocab = schema["vocab"]
    rows = load_rows(Path(args.path))
    errors, warns = [], []

    seen = set()
    for i, r in enumerate(rows, 1):
        where = "row %d" % i
        for k in req:
            if r.get(k) in (None, ""):
                errors.append("%s: missing %s" % (where, k))
        for k, allowed in vocab.items():
            v = str(r.get(k) or "")
            if v and v not in allowed:
                errors.append("%s: %s=%r not in %s" % (where, k, v, allowed))
        for k in ("temp_C", "time_min", "amount", "replicate", "pressure_atm", "lod"):
            v = r.get(k)
            if v in (None, ""):
                continue
            try:
                float(v)
            except Exception:
                errors.append("%s: %s=%r is not numeric" % (where, k, v))
        if str(r.get("replicate") or "") and float(r["replicate"]) < 1:
            errors.append("%s: replicate must be >=1" % where)
        ctype = str(r.get("compound_id_type") or "")
        cid = str(r.get("compound_id") or "")
        if ctype == "inchikey" and cid and not IK.match(cid):
            errors.append("%s: bad InChIKey %r" % (where, cid))
        if ctype == "smiles" and cid:
            try:
                from rdkit import Chem, RDLogger
                RDLogger.DisableLog("rdApp.*")
                if Chem.MolFromSmiles(cid) is None:
                    errors.append("%s: SMILES does not parse %r" % (where, cid))
            except Exception:
                warns.append("%s: rdkit unavailable, SMILES not checked" % where)
        key = (r.get("sample_id"), str(r.get("compound_id") or ""),
               str(r.get("replicate") or ""))
        if all(key):
            if key in seen:
                warns.append("%s: duplicate sample/compound/replicate" % where)
            seen.add(key)
        if str(r.get("detection") or "") == "not_detected" and str(r.get("amount")) not in ("0", "0.0"):
            warns.append("%s: not_detected with amount != 0" % where)
        if ctype == "name_only" and str(r.get("role")) == "product":
            warns.append("%s: name_only product cannot count as an engine hit" % where)
        if str(r.get("source_type")) == "literature" and not str(r.get("citation") or "").strip():
            errors.append("%s: literature row needs a citation" % where)

    print("rows", len(rows))
    print("errors", len(errors), "warnings", len(warns))
    for x in errors[:args.max_print]:
        print("  ERROR", x)
    for x in warns[:args.max_print]:
        print("  WARN ", x)
    if len(errors) > args.max_print:
        print("  ... %d more errors" % (len(errors) - args.max_print))
    print("by source", dict(Counter(str(r.get("source_type")) for r in rows)))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
