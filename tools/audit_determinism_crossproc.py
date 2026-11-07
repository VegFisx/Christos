# -*- coding: utf-8 -*-
r"""
跨进程确定性审计
==================

★ 为什么要单独做这件事

  第 24 轮的确定性审计全在【同一个进程】里跑，
  而同一进程内 PYTHONHASHSEED 是固定的 —— 根本抓不到哈希序问题。

  实测事故：同一个脚本独立进程跑 5 次，产物 462/461/463/458/458。
  固定 PYTHONHASHSEED=0 后变成 452/452/452，才暴露出来。
  根因是 rdchiral 用 set 收集产物（main.py:131）。

★ 做法

  把最小可复现脚本当子进程跑 N 次（不设 PYTHONHASHSEED），
  比对每次的产物集合哈希。全一致才算通过。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PY = r"D:\TCMAI\venv\Scripts\python.exe"
N = 6
# 允许命令行覆盖：快速模式用 3 次就够了（能抓到的还是能抓到）
if "--n" in sys.argv:
    try:
        N = max(2, int(sys.argv[sys.argv.index("--n") + 1]))
    except (IndexError, ValueError):
        pass


def main() -> int:
    print("=" * 88)
    print(f"跨进程确定性审计（跑 {N} 次独立进程，不固定 PYTHONHASHSEED）")
    print("=" * 88)

    script = STAGE / "tools" / "min_repro.py"
    if not script.exists():
        print(f"  ✗ 缺少 {script}")
        return 1

    lines = []
    for i in range(N):
        r = subprocess.run([PY, "-X", "utf8", str(script)],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        hit = next((l for l in r.stdout.splitlines() if l.startswith("COUNT")), None)
        if hit is None:
            print(f"  第{i+1}次 跑失败: {r.stderr[-300:]}")
            return 1
        lines.append(hit.strip())
        print(f"  第{i+1}次: {hit.strip()}")

    uniq = set(lines)
    print()
    if len(uniq) == 1:
        print(f"  ✓ 全部一致（{N}/{N}）")
        print(f"     {lines[0]}")
        ok = True
    else:
        print(f"  ✗ 出现 {len(uniq)} 种不同结果 —— 存在跨进程不确定性")
        for u in uniq:
            print(f"      {u}")
        ok = False

    # 对照：固定哈希种子
    print()
    print("  对照（固定 PYTHONHASHSEED=0）：")
    import os
    env = dict(os.environ, PYTHONHASHSEED="0")
    fixed = []
    for i in range(3):
        r = subprocess.run([PY, "-X", "utf8", str(script)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
        hit = next((l for l in r.stdout.splitlines() if l.startswith("COUNT")), None)
        fixed.append((hit or "?").strip())
    print(f"    {set(fixed)}")

    print()
    print("=" * 88)
    print(f"结果：{'通过' if ok else '失败'}")
    print("=" * 88)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
