# -*- coding: utf-8 -*-
# One-shot: drop the self-defeating "by their characters" clause, add the
# usable denominator to the conclusion, and split the abstract run-on.
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
    ("Glycyrrhiza uralensis resolved to 甘草节 (Gancaojie, a node of the licorice root) rather than to "
     "甘草 (Gancao, the root). The two entries are distinguished here by their romanisation as well as "
     "their characters.",
     "Glycyrrhiza uralensis resolved to 甘草节 (Gancaojie, a node of the licorice root) rather than to "
     "甘草 (Gancao, the root)."),
    ("at depth ≤ 3, 69.0% of targets have at least one usable route.",
     "at depth ≤ 3, 207 of 300 targets (69.0%) have at least one usable route."),
    ("attaches a condition marker and a field-complete provenance record to each candidate; field "
     "completeness does not imply that condition evidence exists, and writes every run as a reproducible "
     "report.",
     "attaches a condition marker and a field-complete provenance record to each candidate. Field "
     "completeness does not imply that condition evidence exists. Every run is written as a reproducible "
     "report."),
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
