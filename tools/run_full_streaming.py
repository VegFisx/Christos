# -*- coding: utf-8 -*-
"""Stream the full pair space to disk in small batches.

The engine's step() returns a whole slice at once, so a 2,000-pair slice holds
~30k Product objects (~1.7 GB).  Calling step() repeatedly with a small
pair_offset window and writing each batch out keeps peak memory flat.

Usage:
    python tools/run_full_streaming.py [--herb 甘草] [--batch 200]
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

import herb as H                 # noqa: E402
import query_base as qb          # noqa: E402
from engine import Compound      # noqa: E402
import templates as T            # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402


def rss_mb():
    try:
        import ctypes
        import ctypes.wintypes as wt

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(
            ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 1048576
    except Exception:
        return -1.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--max-batches", type=int, default=0,
                    help="只跑前 N 批（自测用），0 = 全量")
    args = ap.parse_args()

    cs = H.compounds_of_herb(args.herb, limit=100000)
    subs = [(c.name, c.smiles, c.herb or args.herb) for c in cs if c.smiles]
    n = len(subs)
    total = n * (n - 1) // 2
    print("%s：%d 个成分，%d 对，批 %d" % (args.herb, n, total, args.batch),
          flush=True)

    eng = SmartReactEngine(
        max_pairs=args.batch, max_products_per_pair=8,
        use_curated_templates=True, strict_redox_gate=True,
        mono_redox_gate=True, prefilter=True)
    cond = T.get_template("煎煮")
    compounds = [Compound(smiles=s, name=nm, herb=hb, source="herb")
                 for nm, s, hb in subs]

    out = STAGE / "reports" / "paper" / ("full_stream_%s.jsonl" % args.herb)
    seen = set()
    total_products = 0
    peak = 0.0
    t0 = time.time()
    with out.open("w", encoding="utf-8") as fh:
        stop = total
        if args.max_batches:
            stop = min(total, args.max_batches * args.batch)
        for off in range(0, stop, args.batch):
            eng.pair_offset = off
            got = eng.step(compounds, cond=cond, exclude_smiles=seen,
                           round_no=1)
            for p in got:
                fh.write(json.dumps({
                    "smi": p.smiles, "rule": p.rule_name,
                    "src": p.source_smiles, "herb": p.source_herb,
                    "offset": off}, ensure_ascii=False) + "\n")
                seen.add(p.smiles)
            total_products += len(got)
            del got
            m = rss_mb()
            peak = max(peak, m)
            if (off // args.batch) % 10 == 0:
                print("  offset %6d 累计 %7d 产物  内存 %.0f MB  用时 %.1f 分"
                      % (off, total_products, m, (time.time() - t0) / 60),
                      flush=True)

    print("\n完成：%d 产物（去重后），峰值内存 %.0f MB，总耗时 %.1f 分钟"
          % (total_products, peak, (time.time() - t0) / 60))
    print("输出 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
