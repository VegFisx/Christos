# -*- coding: utf-8 -*-
# One-shot: unify route-found naming and state usable denominators.
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
    # abstract
    ("Multi-step planning reaches 47.67% success at depth ≤ 2 and 72.33% at depth ≤ 3 on 300 ORD targets;",
     "Multi-step planning finds a route for 47.67% of targets at depth ≤ 2 and 72.33% at depth ≤ 3 on 300 "
     "ORD targets;"),
    # methods closing sentence
    ("Success is therefore the looser of the two counts.",
     "Route-found is therefore the looser of the two counts."),
    # results intro to the 300 block
    ("The 300 multi-step targets did not receive the same overlap check. Their success figures are reported "
     "as measured and should be read as not target-level filtered.",
     "The 300 multi-step targets did not receive the same overlap check. Their route-found figures are "
     "reported as measured and should be read as not target-level filtered."),
    # results numbers
    ("With beam width 4 and the selected template library, end-to-end success on the fixed 300-target set is "
     "**47.67%** at depth ≤ 2 (143/300, Wilson 95% CI 42.08–53.31%) and **72.33%** at depth ≤ 3 (217/300, "
     "CI 67.01–77.09%). Of the 217 targets that found a route at depth ≤ 3, 207 have at least one route "
     "marked usable, a usable-target rate of 69.0%. At depth ≤ 2 the usable count was not recorded "
     "separately.",
     "With beam width 4 and the selected template library, the route-found rate on the fixed 300-target set "
     "is **47.67%** at depth ≤ 2 (143/300, Wilson 95% CI 42.08–53.31%) and **72.33%** at depth ≤ 3 "
     "(217/300, CI 67.01–77.09%). At depth ≤ 3, 207 targets have at least one usable route, a "
     "usable-target rate of 207/300 = 69.0% and a usable-given-route-found rate of 207/217 = 95.4%. At "
     "depth ≤ 2 the usable count was not recorded separately."),
    # figure caption
    ("multi-step success at depth ≤ 2 and ≤ 3 (47.67%, 72.33%)",
     "multi-step route-found rate at depth ≤ 2 and ≤ 3 (47.67%, 72.33%)"),
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
