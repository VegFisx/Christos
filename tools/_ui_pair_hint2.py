# -*- coding: utf-8 -*-
# One-shot: replace the pair-budget note with the calibrated wording.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD = ("对子预算 = 底物两两配对的上限。N 个成分有 N×(N−1)/2 对，"
       "4000 约等于 90 个成分的全部配对；超出会按顺序截断，可在高级选项里改成公平截断。")

NEW = ("对子预算 = 底物两两配对的上限，控制的是耗时不是精度。N 个成分有 N×(N−1)/2 对；"
       "实测 4000 对约 4 分钟、5.4 万条产物，8000 对约 10 分钟、12 万条，两者是线性关系，"
       "没有收益递减的拐点。超出会按顺序截断，可在高级选项里改成公平截断。")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(OLD)
    print("hits=%d" % n)
    if n:
        s = s.replace(OLD, NEW, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
