# -*- coding: utf-8 -*-
# One-shot: make the six condition fields visible by default.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

EDITS = [
    ("<div id='condCustom' class='grid3' hidden>",
     "<div id='condCustom' class='grid3'>"),
    ("自定义条件只覆盖填写的项；未填的沿用所选条件档案。",
     "直接填参数；留空的项沿用下方预设的值。预设只是快捷模板，可随时改。"),
    ("<label class='field'>条件档案<select id='cond'>",
     "<label class='field'>基准预设<select id='cond'>"),
]


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(EDITS, 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
