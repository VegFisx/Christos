"""Generate the recorded product of the official USPTO split with the centre model.

Why this exists: the template route reports 92.19% recall on the official 4,993
rows, but recall only says the answer is somewhere in the candidate list. This
script asks a narrower question: with the same reactant, can the learned centre
model write the recorded product down directly, in one shot?

Input rows come from reports/paper/data/uspto50k_official/raw_test.csv, whose
reaction column already carries atom maps, so no mapping step is needed here.
The model is trained separately on RXNMapper-mapped USPTO-50k.

Usage:
    python tools/bench_center_official.py [limit] [model]

Output: prints accuracy overall and per class.
"""
from __future__ import annotations

import csv
import io
import os
import pickle
import sys
from collections import defaultdict
from pathlib import Path

STAGE = Path(__file__).resolve().parents[1]
for sub in ("core", "tools", "libs"):
    sys.path.insert(0, str(STAGE / sub))

from train_center_model import (  # noqa: E402
    _apply,
    _atom_budget,
    _old_orders,
    _to_order_cls,
    canon_set,
)
from build_center_dataset import _row  # noqa: E402

TEST = STAGE / "reports" / "paper" / "data" / "uspto50k_official" / "raw_test.csv"


def _predict(clf, row, pairs, old_ord):
    """Constrained decoding: accept edits high-to-low confidence, skip valence breaks."""
    probs = clf.predict_proba(row["X"])
    budget = _atom_budget(row["smiles_r"])
    cur = {mp: b[0] for mp, b in budget.items()}
    cap = {mp: b[1] for mp, b in budget.items()}
    cand = []
    for j, (a, b) in enumerate(pairs):
        for cls in (1, 2, 3, 4):
            if probs[j][cls] > 0.5:
                cand.append((float(probs[j][cls]), int(a), int(b), cls))
    cand.sort(reverse=True)
    accepted = []
    seen = set()
    for prob, a, b, cls in cand:
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        base = old_ord.get(key, 1.0)
        tgt = _to_order_cls(cls, base)
        delta = tgt - base
        if delta > 0:
            if cur.get(a, 0.0) + delta > cap.get(a, 0.0) + 1e-9:
                continue
            if cur.get(b, 0.0) + delta > cap.get(b, 0.0) + 1e-9:
                continue
        cur[a] = cur.get(a, 0.0) + delta
        cur[b] = cur.get(b, 0.0) + delta
        seen.add(key)
        accepted.append((a, b, tgt))
    if not accepted:
        return None
    return _apply(row["smiles_r"], accepted, row["smiles_p"])


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    model_path = sys.argv[2] if len(sys.argv) > 2 else "reports/center_model_uspto.pkl"
    with open(STAGE / model_path, "rb") as fh:
        clf = pickle.load(fh)

    n = hit = invalid = skipped = 0
    by_class = defaultdict(lambda: [0, 0])
    with io.open(TEST, encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            if limit and n >= limit:
                break
            parts = (rec.get("reactants>reagents>production") or "").split(">")
            if len(parts) != 3:
                skipped += 1
                continue
            lhs, _reagents, rhs = parts
            row = _row(rec["id"], lhs + ">>" + rhs)
            if row is None:
                skipped += 1
                continue
            got = _predict(clf, row, row["pair_idx"], _old_orders(row["smiles_r"]))
            want = canon_set(rhs)
            cls = rec.get("class") or "?"
            by_class[cls][1] += 1
            n += 1
            if got is None:
                invalid += 1
            elif got == want:
                hit += 1
                by_class[cls][0] += 1

    print(f"rows {n}, skipped {skipped}, invalid structures {invalid}")
    print(f"product exact {hit}/{n} = {hit / max(n, 1):.1%}")
    for cls in sorted(by_class, key=lambda x: (len(x), x)):
        h, t = by_class[cls]
        print(f"  class {cls}: {h}/{t} = {h / max(t, 1):.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
