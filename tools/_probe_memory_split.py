# -*- coding: utf-8 -*-
# One-shot: where does a worker's memory go?
import os
import sys
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


def rss_mb():
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1048576
    except Exception:
        pass
    # 无 psutil 时用 Windows API
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
        h = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 1048576
    except Exception:
        return -1.0


def main() -> int:
    print("baseline %.0f MB" % rss_mb())

    import herb as H
    import query_base as qb
    cs = H.compounds_of_herb("甘草", limit=100000)
    seeds = [(c.name, c.smiles, "tcm.db:甘草") for c in cs if c.smiles]
    print("after seeds (%d) %.0f MB" % (len(seeds), rss_mb()))

    spec = qb.RunSpec(seeds=seeds, cond_name="煎煮", rounds=1,
                      max_pairs=2000, max_products_per_pair=8,
                      use_curated_templates=True, strict_redox_gate=True,
                      pair_offset=0)
    inv = qb.build_inventory(spec, score=False, use_cache=False, ik_workers=1)
    print("after slice (%d products) %.0f MB" % (len(inv.paths), rss_mb()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
