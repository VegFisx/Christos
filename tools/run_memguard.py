# -*- coding: utf-8 -*-
"""带内存护栏地跑一条命令：超过上限就杀掉整个进程树。

为什么有它：2026-11-13 用 6 个 worker 跑「模板全装」的基准，单 worker 内存
远比生产配置高，叠加 50k 数据构建把 16 GB 机器打爆。以后所有重活都走这里。

用法：
  python tools\\run_memguard.py --limit-gb 11 -- python -I tools\\paper_bench_official_test.py 6
  python tools\\run_memguard.py --limit-gb 11 --log _diag\\run.log -- <命令...>

行为：
  - 每秒采样整棵进程树的 RSS；超过 --limit-gb 立即 terminate 并返回退出码 3；
  - 正常结束返回子进程退出码；
  - 打印峰值 RSS 与耗时。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import psutil
except Exception:                                      # noqa: BLE001
    print("[memguard] 没有 psutil，无法设护栏；拒绝运行", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-gb", type=float, default=11.0)
    ap.add_argument("--log", default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("用法：python tools\\run_memguard.py --limit-gb 11 -- <命令...>")
        return 2

    limit = a.limit_gb * 1e9
    log = open(a.log, "w", encoding="utf-8") if a.log else None
    t0 = time.time()
    p = subprocess.Popen(cmd, stdout=log or sys.stdout, stderr=subprocess.STDOUT)
    proc = psutil.Process(p.pid)
    peak = 0
    killed = False
    while p.poll() is None:
        try:
            tot = proc.memory_info().rss
            for c in proc.children(recursive=True):
                try:
                    tot += c.memory_info().rss
                except psutil.Error:
                    pass
            peak = max(peak, tot)
            if tot > limit:
                print("\n[memguard] 峰值 %.2f GB 超过上限 %.2f GB，终止进程树"
                      % (tot / 1e9, a.limit_gb), file=sys.stderr)
                for c in proc.children(recursive=True):
                    try:
                        c.kill()
                    except psutil.Error:
                        pass
                proc.kill()
                killed = True
                break
        except psutil.Error:
            pass
        time.sleep(1.0)
    rc = p.wait()
    if log:
        log.close()
    print("[memguard] 峰值 RSS %.2f GB / 上限 %.2f GB / 墙钟 %.1f s / 退出码 %s"
          % (peak / 1e9, a.limit_gb, time.time() - t0, rc))
    return 3 if killed else int(rc or 0)


if __name__ == "__main__":
    raise SystemExit(main())
