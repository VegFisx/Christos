# -*- coding: utf-8 -*-
# One-shot: decouple the herb-audit argument from bare Chinese glyphs, and
# bring the conclusion in line with route-found naming.
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
    ("Glycyrrhiza uralensis resolved to 甘草节 (a node of the licorice root), rather than to 甘草.",
     "Glycyrrhiza uralensis resolved to 甘草节 (Gancaojie, a node of the licorice root) rather than to "
     "甘草 (Gancao, the root). The two entries are distinguished here by their romanisation as well as "
     "their characters."),
    ("The single character 甘 returned 40 candidates, the substring cap, because it matches many herb names.",
     "The single character 甘 (gan) returned 40 candidates, the substring cap, because it matches many herb "
     "names."),
    ("On the leak-controlled USPTO-50k benchmark the selected configuration reaches 82.32% single-step "
     "recall. Reverse search reaches 94.74% coverage on the 5,002-target subset and 79.81% on the full "
     "50,016 targets, and multi-step planning reaches 47.67% and 72.33% at depth ≤ 2 and ≤ 3 on a "
     "300-target ORD set that has not been target-level filtered.",
     "On the leak-controlled USPTO-50k benchmark the selected configuration reaches 82.32% single-step "
     "recall. Reverse search reaches 94.74% coverage on the 5,002-target subset and 79.81% on the full "
     "50,016 targets. Multi-step route-found rate is 47.67% at depth ≤ 2 and 72.33% at depth ≤ 3 on a "
     "300-target ORD set that has not been target-level filtered; at depth ≤ 3, 69.0% of targets have at "
     "least one usable route."),
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
