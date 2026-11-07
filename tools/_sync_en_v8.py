# -*- coding: utf-8 -*-
# One-shot: define multi-step success vs usability.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

EDITS = [
    ("A route counts as usable when every step passes the step-usability check in "
     "retro_search.step_usability; a target counts as usable when at least one route does.",
     "A target counts as successful when the search returns at least one route, whether or not that route "
     "passes the usability check. A route counts as usable when every step passes the step-usability check "
     "in retro_search.step_usability; a target counts as usable when at least one of its routes does. "
     "Success is therefore the looser of the two counts."),
    ("Of those 300 targets, 207 have at least one route marked usable.",
     "Of the 217 targets that succeeded at depth ≤ 3, 207 have at least one route marked usable."),
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
