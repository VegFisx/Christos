# -*- coding: utf-8 -*-
# One-shot: warn that the all-compounds tier can exhaust memory.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD = ("128 个约 7.1 分钟（实测）；全部约 57 分钟（外推）")
NEW = ("128 个约 7.1 分钟（实测）；全部 359 个在 64,261 对规模下曾因内存耗尽而中断，"
       "建议先存盘再跑，或改用 128")

OLD2 = ("128 个约 7.1 分钟（实测），全部约 57 分钟（外推）")
NEW2 = ("128 个约 7.1 分钟（实测）；全部 359 个曾因内存耗尽中断，建议先存盘或改用 128")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(OLD)
    n2 = s.count(OLD2)
    print("hits %d %d" % (n1, n2))
    if n1:
        s = s.replace(OLD, NEW, 1)
    if n2:
        s = s.replace(OLD2, NEW2, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
