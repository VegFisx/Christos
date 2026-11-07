# -*- coding: utf-8 -*-
# One-shot: report truncation implied by the candidate distributions.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

ANCHOR = "The extra candidates are part of the explanation, so recall and candidate count have to be read together. Moving from the baseline to the selected configuration raises both."

ADD = (ANCHOR + "\n\n"
       "Truncation is substantial in both runs. At the baseline cap of 8 the median candidate count is "
       "exactly 8, so at least half of the reactions hit the cap. At the selected cap of 32 the 90th "
       "percentile is exactly 32, so at least a tenth do. A recall figure measured on a capped run is "
       "therefore a lower bound on the uncapped value, and the true figure is unknown from these runs.")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("hits=%d" % n)
    if n:
        s = s.replace(ANCHOR, ADD, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
