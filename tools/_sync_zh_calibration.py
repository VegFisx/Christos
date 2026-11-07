# -*- coding: utf-8 -*-
# One-shot: add the runtime calibration section to the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

SECTION = "\n".join([
    "### 运行时标定",
    "",
    "两个预算控制一次运行：每味成分上限和对子预算。两者都在甘草上实测，不是凭感觉定的。",
    "",
    "| 成分上限 | 底物 | 对子 | 产物 | 耗时 |",
    "|---|---:|---:|---:|---:|",
    "| 24 | 24 | 276 | 3,666 | 18.5 s |",
    "| 64 | 64 | 2,016 | 33,579 | 166 s |",
    "| 128 | 128 | 8,128 | 97,670 | 429 s |",
    "",
    "24 个成分就覆盖甘草全部 17 个 marker。加到 128 只增加产物、不增加 marker，"
    "所以 marker 级别的工作用 24，大档留给穷举。",
    "",
    "| 对子预算 | 实际对 | 产物 | 耗时 |",
    "|---|---:|---:|---:|",
    "| 500 | 500 | 9,914 | 50 s |",
    "| 1,000 | 1,000 | 17,826 | 77 s |",
    "| 2,000 | 2,000 | 27,076 | 109 s |",
    "| 4,000 | 4,000 | 54,103 | 259 s |",
    "| 8,000 | 8,000 | 120,487 | 573 s |",
    "",
    "产物数和耗时都随对子线性增长，没有效率拐点。对子预算换的是等待时间，不是质量。",
    "",
    "全量 58,311 对无法一次跑完：引擎在单进程内累积全部产物，规模到十万级时内存吃不消。"
    "因此改成切片执行，每 2,000 对写一个检查点，崩溃后从断点继续。切片内去重、跨片不去重，"
    "所以产物总数是上界。",
    "",
])

ANCHOR = "## 讨论"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor=%d" % n)
    if n:
        s = s.replace(ANCHOR, SECTION + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
