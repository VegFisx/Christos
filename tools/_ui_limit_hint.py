# -*- coding: utf-8 -*-
# One-shot: add calibrated timing to the component-limit field.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD_TITLE = ("title='成分越多覆盖越全也越慢；排序为 marker 优先、分子量降序'")
NEW_TITLE = ("title='实测（甘草）：3/6/12/24/48 个成分分别约 1/2/4/19/93 秒，"
             "产物数随成分数的平方增长；排序为 marker 优先、分子量降序'")

ANCHOR = ("<span class='hint'>对子预算 = 底物两两配对的上限，控制的是耗时不是精度。")
INSERT = "\n".join([
    "    </div>",
    "    <div class='row' style='font-size:12px;color:var(--muted)'>",
    "      <span class='hint'>每味成分实测（甘草）：3 / 6 / 12 / 24 / 48 个分别约 1 / 2 / 4 / 19 / 93 秒；"
    "产物数随成分数的平方增长。默认取全部，按需下调可以明显缩短等待。</span>",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(OLD_TITLE)
    print("title hits=%d" % n1)
    s = s.replace(OLD_TITLE, NEW_TITLE, 1)
    idx = s.find(ANCHOR)
    if idx > 0:
        # close the current row, then open a new one with the limit note,
        # immediately before the pair-budget narration starts
        row_start = s.rfind("<div class='row'", 0, idx)
        s = s[:row_start] + INSERT.lstrip("\n") + "\n    " + s[row_start:]
        print("inserted")
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
