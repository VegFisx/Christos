# -*- coding: utf-8 -*-
"""Run the full pair space with several worker processes.

Each worker owns one slice of the pair space and builds its own engine, so no
state is shared.  The script then compares its per-slice product counts with
the serial checkpoints to confirm the two paths agree.

Usage:
    python tools/run_full_parallel.py [--herb 甘草] [--slice 2000] [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
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

_G = {}


def _init(herb):
    for _p in ("core", "rules", "libs", "tools", "sources", "conditions"):
        d = STAGE / _p
        if d.is_dir() and str(d) not in sys.path:
            sys.path.insert(0, str(d))
    import herb as H
    import query_base as qb
    cs = H.compounds_of_herb(herb, limit=100000)
    _G["seeds"] = [(c.name, c.smiles, "tcm.db:%s" % (c.herb or herb))
                   for c in cs if c.smiles]
    _G["qb"] = qb


def _work(job):
    offset, size = job
    qb = _G["qb"]
    t0 = time.time()
    spec = qb.RunSpec(
        seeds=_G["seeds"], cond_name="煎煮", rounds=1,
        max_pairs=size, max_products_per_pair=8,
        use_curated_templates=True, strict_redox_gate=True,
        pair_offset=offset,
    )
    inv = qb.build_inventory(spec, score=False, use_cache=False, ik_workers=1)
    return {"offset": offset, "products": len(inv.paths),
            "seconds": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    ap.add_argument("--slice", type=int, default=2000)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    import herb as H
    n = len([c for c in H.compounds_of_herb(args.herb, limit=100000) if c.smiles])
    total = n * (n - 1) // 2
    jobs = [(o, args.slice) for o in range(0, total, args.slice)]
    print("%s：%d 个成分，%d 对，%d 个切片，%d 进程"
          % (args.herb, n, total, len(jobs), args.workers), flush=True)

    t0 = time.time()
    ctx = mp.get_context("spawn")
    rows = []
    with ctx.Pool(processes=args.workers, initializer=_init,
                  initargs=(args.herb,)) as pool:
        for k, r in enumerate(pool.imap_unordered(_work, jobs), 1):
            rows.append(r)
            print("  完成 %2d/%d：offset=%5d products=%6d %.1fs（累计 %.1f 分）"
                  % (k, len(jobs), r["offset"], r["products"], r["seconds"],
                     (time.time() - t0) / 60), flush=True)

    rows.sort(key=lambda r: r["offset"])
    total_products = sum(r["products"] for r in rows)
    print("\n并行产物合计 %d，总耗时 %.1f 分钟"
          % (total_products, (time.time() - t0) / 60))

    ck = STAGE / "reports" / "paper" / ("full_slices_%s.jsonl" % args.herb)
    if ck.exists():
        serial = [json.loads(x) for x in ck.read_text(encoding="utf-8").splitlines()
                  if x.strip()]
        serial.sort(key=lambda r: r["offset"])
        same = len(serial) == len(rows) and all(
            a["offset"] == b["offset"] and a["products"] == b["products"]
            for a, b in zip(serial, rows))
        print("与串行结果比对：%s（串行合计 %d）"
              % ("完全一致" if same else "不一致", sum(r["products"] for r in serial)))
        if not same:
            for a, b in zip(serial, rows):
                if a["products"] != b["products"]:
                    print("   差异 offset=%d 串行=%d 并行=%d"
                          % (a["offset"], a["products"], b["products"]))

    out = STAGE / "reports" / "paper" / ("full_parallel_%s.json" % args.herb)
    out.write_text(json.dumps({"rows": rows,
                               "total_products": total_products,
                               "seconds": round(time.time() - t0, 1)},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
