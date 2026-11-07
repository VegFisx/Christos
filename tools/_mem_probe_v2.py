# -*- coding: utf-8 -*-
# 一次性：量"v2 大库单 worker"的内存足迹（本进程自测；单进程运行，避免再压爆内存）
import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


class MS(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def proc_mem():
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    ctypes.WinDLL("psapi").GetProcessMemoryInfo(
        ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 2 ** 20, pmc.PeakWorkingSetSize / 2 ** 20


def sys_free():
    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return ms.ullAvailPhys / 2 ** 30, ms.ullTotalPhys / 2 ** 30


STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

free0, tot = sys_free()
print("系统：总 %.1f GB · 可用 %.1f GB" % (tot, free0))

from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions
RDLogger.DisableLog("rdApp.*")
cur, peak = proc_mem()
print("导入 rdkit 后：进程 %.0f MB（峰值 %.0f）" % (cur, peak))

t0 = time.time()
lib = []
for line in open(STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl_v2.jsonl",
                 encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    try:
        rx = rdChemReactions.ReactionFromSmarts(r["template"])
    except Exception:
        rx = None
    if rx is None or rx.GetNumReactantTemplates() != 1:
        continue
    lib.append((str(r["template"]), int(r.get("freq") or 0), rx))
cur, peak = proc_mem()
print("编译 %d 条模板后：进程 %.0f MB（峰值 %.0f）· 用时 %.0fs"
      % (len(lib), cur, peak, time.time() - t0))

import retro_search as rs
tg = []
for i, line in enumerate(open(STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl",
                              encoding="utf-8")):
    if line.strip():
        tg.append(json.loads(line)["product"])
    if i >= 300:
        break
tg = tg[::10][:30]
t0 = time.time()
cuts = 0
for smi in tg:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        continue
    for sm, fr, rx in lib:
        try:
            outs = rx.RunReactants((m,))
        except Exception:
            continue
        cuts += len(outs)
cur, peak = proc_mem()
free1, _ = sys_free()
print("再跑 30 个目标（%d 切断）后：进程 %.0f MB（峰值 %.0f）· 用时 %.0fs"
      % (cuts, cur, peak, time.time() - t0))
print("系统可用内存：%.1f -> %.1f GB" % (free0, free1))
print("【单 worker 峰值内存 ≈ %.1f GB（含 python 基础占用）】" % (peak / 1024))
