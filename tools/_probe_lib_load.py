# -*- coding: utf-8 -*-
r"""一次性探针：测"逆模板库加载代价"（v2 生产化选型用）。

用法:
  python tools\_probe_lib_load.py                # 默认测三档：老库 / freq>=10 / v2 全量
  python tools\_probe_lib_load.py <lib1.jsonl> ...

* 每个库在**独立子进程**里加载（互不污染内存峰值），走的就是引擎真实路径：
  retro_search.load_rdchiral_templates（rdChemReactions 逐条编译）。
* 输出：每库 行数 / 编译成功 / 跳过 / 加载秒数 / 进程峰值 RSS(MB)。
* 只读；不写任何库文件。
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
LIBS = [
    STAGE / "reports" / "retro_templates_clustered.jsonl",              # 老生产库 3,228
    STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl_v2_freq10.jsonl",  # 18,232
    STAGE / "reports" / "paper" / "data" / "lib_full_v2.jsonl",         # 81,286
]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


def peak_rss_mb() -> float:
    # argtypes 必须显式设定，否则 GetProcessMemoryInfo 返回 0（实测踩过）
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                   ctypes.c_ulong]
    fn.restype = ctypes.c_bool
    pmc = PROCESS_MEMORY_COUNTERS()
    pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
    h = ctypes.windll.kernel32.GetCurrentProcess()
    if not fn(h, ctypes.byref(pmc), pmc.cb):
        return -1.0
    return pmc.PeakWorkingSetSize / 1048576.0


def child(path: str) -> int:
    import time
    sys.path.insert(0, str(STAGE / "tools"))
    sys.path.insert(0, str(STAGE / "core"))
    import retro_search as rs
    t0 = time.time()
    tpl = rs.load_rdchiral_templates(Path(path))
    dt = time.time() - t0
    n_lines = sum(1 for l in open(path, encoding="utf-8") if l.strip())
    print(json.dumps({"lib": Path(path).name, "n_lines": n_lines, "n_ok": len(tpl),
                      "n_bad": n_lines - len(tpl), "load_s": round(dt, 1),
                      "peak_rss_mb": round(peak_rss_mb(), 0)}, ensure_ascii=False))
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--child"]
    paths = [Path(a) for a in args] or LIBS
    print("每库独立子进程（真实加载路径 retro_search.load_rdchiral_templates）")
    for p in paths:
        if not p.exists():
            print("  跳过（不存在）：%s" % p)
            continue
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                            "--child", str(p)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=1800)
        line = (r.stdout or "").strip().splitlines()
        print("  %s" % (line[-1] if line else "（无输出，stderr=%s）" % (r.stderr or "")[-300:]))
    return 0


if __name__ == "__main__":
    if "--child" in sys.argv:
        sys.exit(child(sys.argv[sys.argv.index("--child") + 1]))
    sys.exit(main())
