"""Build the atom-pair centre dataset from RXNMapper-mapped USPTO-50k reactions.

Why a separate builder: build_center_dataset.py reads the ORD shards, which carry
integer-mapped reactions in the same "reactants>>products" form. The RXNMapper
output is the same form but arrives in its own file with a confidence score, so
this script reuses the row builder and only replaces the source.

The confidence filter is the point: a mapping below the threshold is not a fact,
it is a guess, and training on guesses would teach the model the mapper's noise.
Rows dropped by the filter are counted and printed.

Usage:
    python tools/build_center_uspto.py [rows] [min_confidence]

Output: reports/center_dataset_uspto.jsonl
"""
from __future__ import annotations

import io
import json
import random
import sys
from pathlib import Path

STAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGE / "core"))
sys.path.insert(0, str(STAGE / "tools"))

from build_center_dataset import _row  # noqa: E402

MAPPED = STAGE / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
OUT = STAGE / "reports" / "center_dataset_uspto.jsonl"


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    min_conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    rng = random.Random(20261111)

    kept = 0
    low_conf = 0
    failed = 0
    label_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    n_pairs = 0

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        for line in io.open(MAPPED, encoding="utf-8"):
            if kept >= limit:
                break
            rec = json.loads(line)
            conf = float(rec.get("confidence") or 0.0)
            if conf < min_conf:
                low_conf += 1
                continue
            row = _row(str(rec.get("id")), str(rec.get("mapped_rxn") or ""))
            if row is None:
                failed += 1
                continue
            # Downsample the unchanged pairs the same way the ORD builder does:
            # left at 99% "unchanged" the model learns to answer 0 to everything.
            pos = [i for i, v in enumerate(row["y"]) if v != 0]
            neg = [i for i, v in enumerate(row["y"]) if v == 0]
            if not pos:
                failed += 1
                continue
            keep_neg = rng.sample(neg, min(len(neg), 8 * len(pos)))
            keep = sorted(pos + keep_neg)
            row["X"] = [row["X"][i] for i in keep]
            row["y"] = [row["y"][i] for i in keep]
            row["pair_idx"] = [row["pair_idx"][i] for i in keep]
            row["conf"] = round(conf, 4)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            kept += 1
            for y in row["y"]:
                label_counts[int(y)] = label_counts.get(int(y), 0) + 1
            n_pairs += len(row["y"])

    print(f"kept {kept} reactions, {n_pairs} pairs")
    print(f"skipped: low_confidence {low_conf}, unparsable {failed}")
    print(f"labels {label_counts}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
