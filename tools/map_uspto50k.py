"""Map the USPTO-50k corpus with RXNMapper (CPU, batched).

Why this exists: the centre-pair model (core/center_apply2.py, tools/
train_center_model.py) learns from atom-mapped reactions, and the shipped
benchmarks run on USPTO templates. The USPTO corpus in this repository has no
atom maps at all (checked: 0/2,000 reactions carry ":"), so the model could
only ever be trained on ORD, which is a different corpus.

RXNMapper supplies exactly the missing piece: algorithmic atom mapping that is
declared as such, so a model trained on it can be reported honestly.

Usage:
    set HF_ENDPOINT=https://hf-mirror.com
    python tools/map_uspto50k.py 50000

Reads  reports/paper/data/uspto50k_canon.jsonl  (fields: id, reactants, product)
Writes reports/paper/data/uspto50k_mapped.jsonl (fields: id, mapped_rxn, confidence)
"""

import io
import json
import os
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
STAGE = _HERE.parent
LIBMAP = Path(r"D:\ProgramData\DSHNS\_rxnmapper_libs")
if LIBMAP.is_dir():
    sys.path.insert(0, str(LIBMAP))

SRC = STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
DST = STAGE / "reports" / "paper" / "data" / "uspto50k_mapped.jsonl"
BATCH = int(os.environ.get("MAP_BATCH") or 32)


def _j(v):
    return ".".join(v) if isinstance(v, list) else str(v)


def main() -> int:
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

    rows = []
    with io.open(SRC, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break

    from rxnmapper import RXNMapper

    mapper = RXNMapper()
    t0 = time.time()
    done = 0
    bad = 0
    with io.open(DST, "w", encoding="utf-8", newline="\n") as out:
        for i in range(0, len(rows), BATCH):
            chunk = rows[i:i + BATCH]
            rxns = []
            keep = []
            for r in chunk:
                lhs = _j(r.get("reactants", ""))
                rhs = _j(r.get("product", ""))
                if not lhs or not rhs:
                    bad += 1
                    continue
                rxns.append(lhs + ">>" + rhs)
                keep.append(r)
            if not rxns:
                continue
            try:
                res = mapper.get_attention_guided_atom_maps(rxns)
            except Exception as exc:  # one bad row should not kill the batch
                print("[warn] batch %d failed: %s" % (i, exc), flush=True)
                bad += len(rxns)
                continue
            for r, x in zip(keep, res):
                out.write(json.dumps({
                    "id": r.get("id"),
                    "mapped_rxn": x.get("mapped_rxn", ""),
                    "confidence": round(float(x.get("confidence") or 0.0), 4),
                }, ensure_ascii=False) + "\n")
                done += 1
            if (i // BATCH) % 20 == 0:
                dt = time.time() - t0
                rate = done / dt if dt else 0.0
                print("mapped %d/%d  %.1f rx/s  eta %.0f min"
                      % (done, len(rows), rate, (len(rows) - done) / rate / 60 if rate else 0),
                      flush=True)

    print("done %d mapped, %d skipped, %.1f min -> %s"
          % (done, bad, (time.time() - t0) / 60.0, DST), flush=True)
    confs = []
    with io.open(DST, encoding="utf-8") as fh:
        for line in fh:
            confs.append(json.loads(line)["confidence"])
    if confs:
        confs.sort()
        print("confidence: median %.3f  p10 %.3f  <0.5 %d/%d"
              % (confs[len(confs) // 2], confs[int(len(confs) * 0.1)],
                 sum(1 for c in confs if c < 0.5), len(confs)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
