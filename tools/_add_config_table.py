# -*- coding: utf-8 -*-
# One-shot: insert the experiment-configuration table into the English draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")
ANCHOR = "## Results"

TABLE = "\n".join([
    "### Experiment configuration",
    "",
    "| Experiment | Target set | Template library | Product-level filter | Comparable with |",
    "|---|---|---|---|---|",
    "| Forward, baseline | 50,016 USPTO-50k | engine default | yes, on USPTO-50k | forward selected |",
    "| Forward, selected | 50,016 USPTO-50k | ~20,000 support-filtered | yes, on USPTO-50k | forward baseline |",
    "| Reverse, subset | 5,002 ORD | 79,184 | yes, plus target overlap check | nothing else |",
    "| Reverse, full | 50,016 USPTO-50k | 3,065 | yes | nothing else |",
    "| Multi-step | 300 ORD | selected | no target overlap check | nothing else |",
    "| Condition audit | 500 templates | production | not applicable | nothing else |",
    "| Herb resolution | 75 fixed inputs | not applicable | not applicable | nothing else |",
    "",
    "The forward experiments share a target set and differ only in configuration, so their comparison is "
    "meaningful. The two reverse experiments differ in both target set and library and are reported side by "
    "side only for completeness. The multi-step run inherits the selected library but has not been checked "
    "for target-level overlap.",
    "",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor hits=%d" % n)
    if n:
        s = s.replace(ANCHOR, TABLE + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("inserted, %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
