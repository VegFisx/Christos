# -*- coding: utf-8 -*-
# One-shot: let the browser skip off-screen rows in the big product table.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\make_report.py")

CSS = "tbody tr{content-visibility:auto;contain-intrinsic-size:auto 128px}"


def main() -> int:
    lines = P.read_text(encoding="utf-8").splitlines()
    out = []
    added = 0
    for ln in lines:
        out.append(ln)
        if "th{background:#eef1f5" in ln and added == 0:
            indent = ln[:len(ln) - len(ln.lstrip())]
            out.append(indent + '"%s",' % CSS)
            added += 1
    P.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print("added=%d lines=%d" % (added, len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
