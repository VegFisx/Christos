# -*- coding: utf-8 -*-
"""测宽档单进程内存随处理条数的增长（第 105 轮）。

背景：宽档全量基准两次在不同时间点「静止不动」，都在单 worker 内存 3~4.6 GB 时发生。
本脚本在同一进程里连跑 N 条反应，每 50 条打印一次 RSS，用来判断是「某条反应爆炸」
还是「每条反应漏一点」。

用法：
    python -I tools/diag_bench_memory.py --n 300 --step 50
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "tools" / "paper_bench_50k_forward.py"


def rss_mb() -> float:
    try:
        import psutil  # type: ignore
        return psutil.Process().memory_info().rss / 1e6
    except Exception:
        pass
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        pass
    # Windows 兜底：ctypes
    import ctypes
    import ctypes.wintypes as wt

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                             ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 1e6


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--step", type=int, default=50)
    ap.add_argument("--shard", default="0/8")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("bench", str(BENCH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    sample = []
    by_cls = {}
    for line in open(mod.TARGETS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        by_cls.setdefault(str(r["class"]), []).append(r)
    rng = random.Random(mod.SEED)
    for c, lst in sorted(by_cls.items()):
        rng.shuffle(lst)
        sample.extend(lst[:100000])
    sample.sort(key=lambda r: r["i"])
    si, sn = (int(x) for x in a.shard.split("/"))
    sample = [r for k, r in enumerate(sample) if k % sn == si]
    sample = sample[: a.n]

    sys.path.insert(0, str(ROOT / "core"))
    sys.path.insert(0, str(ROOT / "conditions"))
    sys.path.insert(0, str(ROOT))
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    t0 = time.time()
    eng = SmartReactEngine(extra_template_min_support=1, extra_template_limit=60000,
                           mono_template_limit=20000, mono_include_co_reagent=True,
                           max_products_per_pair=128)
    cond = T.get_template("煎煮")
    print("engine ready %.1fs rss=%.0f MB" % (time.time() - t0, rss_mb()), flush=True)

    t1 = time.time()
    for k, rec in enumerate(sample, 1):
        comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
                 for j, s in enumerate(rec["reactants"])]
        try:
            eng.step(comps, cond, round_no=1)
        except Exception as ex:
            print("  ERR %s %s" % (rec["i"], type(ex).__name__))
        if k % a.step == 0:
            dt = time.time() - t1
            print("%5d  rss=%6.0f MB  %.1f 条/s" % (k, rss_mb(), k / max(dt, 1e-9)), flush=True)
    print("done %.1fs" % (time.time() - t1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
