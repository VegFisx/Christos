# -*- coding: utf-8 -*-
# One-shot: close the row div that the limit note left open.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD = ("默认取全部，按需下调可以明显缩短等待。</span>\n"
       "    <div class='row' style='font-size:12px;color:var(--muted)'>")
NEW = ("默认取全部，按需下调可以明显缩短等待。</span>\n"
       "    </div>\n"
       "    <div class='row' style='font-size:12px;color:var(--muted)'>")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(OLD)
    print("hits=%d" % n)
    if n:
        s = s.replace(OLD, NEW, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
    print("open=%d close=%d" % (s.count("<div"), s.count("</div>")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
