# -*- coding: utf-8 -*-
# One-shot: add a visible note explaining the pair budget.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

ANCHOR = ("<span class='hint'>直接填参数；留空的项沿用下方预设的值。"
          "预设只是快捷模板，可随时改。</span>")

NOTE = "\n".join([
    ANCHOR,
    "    </div>",
    "    <div class='row' style='font-size:12px;color:var(--muted)'>",
    "      <span class='hint'>对子预算 = 底物两两配对的上限。N 个成分有 N×(N−1)/2 对，"
    "4000 约等于 90 个成分的全部配对；超出会按顺序截断，可在高级选项里改成公平截断。</span>",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor hits=%d" % n)
    if n:
        s = s.replace(ANCHOR, NOTE, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
