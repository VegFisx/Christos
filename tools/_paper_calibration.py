# -*- coding: utf-8 -*-
# One-shot: add runtime calibration tables to the manuscript.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

SECTION = "\n".join([
    "### Runtime calibration",
    "",
    "Two budgets govern a run: the per-herb component limit and the per-pair cap on "
    "substrate pairs. Both were measured on Glycyrrhiza rather than chosen by feel.",
    "",
    "| Component limit | Substrates | Pairs | Products | Time |",
    "|---|---:|---:|---:|---:|",
    "| 24 | 24 | 276 | 3,666 | 18.5 s |",
    "| 64 | 64 | 2,016 | 33,579 | 166 s |",
    "| 128 | 128 | 8,128 | 97,670 | 429 s |",
    "",
    "At 24 compounds a run covers all 17 marker compounds of Glycyrrhiza. Going to 128 "
    "adds products but no new markers, so the useful default for marker-level work is 24 "
    "and the larger tiers exist for exhaustive enumeration.",
    "",
    "| Pair budget | Effective pairs | Products | Time |",
    "|---|---:|---:|---:|",
    "| 500 | 500 | 9,914 | 50 s |",
    "| 1,000 | 1,000 | 17,826 | 77 s |",
    "| 2,000 | 2,000 | 27,076 | 109 s |",
    "| 4,000 | 4,000 | 54,103 | 259 s |",
    "| 8,000 | 8,000 | 120,487 | 573 s |",
    "",
    "Products scale with pairs and time scales with pairs, with no efficiency cliff in "
    "between. The pair budget therefore trades waiting time for coverage; it is not a "
    "quality threshold.",
    "",
])

ANCHOR = "## Discussion"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor=%d" % n)
    if n:
        s = s.replace(ANCHOR, SECTION + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
