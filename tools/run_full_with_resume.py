# -*- coding: utf-8 -*-
"""Walk the full pair space in slices so a crash does not lose everything.

Each slice is written to a checkpoint file.  On restart the script continues
from the last completed offset.

Usage:
    python tools/run_full_with_resume.py [--herb 甘草] [--slice 2000]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
for _p in ("core", "rules", "libs", "tools", "sources", "conditions"):
    d = STAGE / _p
    if d.is_dir() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

import herb as H          # noqa: E402
import query_base as qb   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    ap.add_argument("--slice", type=int, default=2000)
    args = ap.parse_args()

    cs = H.compounds_of_herb(args.herb, limit=100000)
    seeds = [(c.name, c.smiles, "tcm.db:%s" % (c.herb or args.herb))
             for c in cs if c.smiles]
    n = len(seeds)
    total_pairs = n * (n - 1) // 2
    print("%s：%d 个成分，%d 对，切片 %d" % (args.herb, n, total_pairs, args.slice),
          flush=True)

    ckpt = STAGE / "reports" / "paper" / (
        "full_slices_%s.jsonl" % args.herb)
    done = set()
    if ckpt.exists():
        for line in ckpt.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["offset"])
        print("已有 %d 个切片，继续" % len(done), flush=True)

    t_all = time.time()
    with ckpt.open("a", encoding="utf-8") as fh:
        for offset in range(0, total_pairs, args.slice):
            if offset in done:
                continue
            t0 = time.time()
            spec = qb.RunSpec(
                seeds=seeds, cond_name="煎煮", rounds=1,
                max_pairs=args.slice, max_products_per_pair=8,
                use_curated_templates=True, strict_redox_gate=True,
                pair_offset=offset,
            )
            inv = qb.build_inventory(spec, score=False, use_cache=False)
            rec = {"offset": offset, "capped": args.slice,
                   "products": len(inv.paths),
                   "seconds": round(time.time() - t0, 1)}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            print("  切片 %6d -> %6d 产物，%6.1f 秒（累计 %.0f 分）"
                  % (offset, len(inv.paths), rec["seconds"],
                     (time.time() - t_all) / 60), flush=True)

    rows = [json.loads(x) for x in ckpt.read_text(encoding="utf-8").splitlines() if x.strip()]
    print("\n切片 %d 个，产物合计 %d（切片内去重，切片间未去重）"
          % (len(rows), sum(r["products"] for r in rows)))
    print("总耗时 %.1f 分钟" % ((time.time() - t_all) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
