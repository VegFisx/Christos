# -*- coding: utf-8 -*-
# One-shot: ninth-round reviewer fixes.
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
    # abstract: reverse figures are not comparable
    ("and 79.81% on the full 50,016 targets with the 3,065-template leak-controlled library.",
     "and 79.81% on the full 50,016 targets with the 3,065-template leak-controlled library; these two "
     "figures are not directly comparable because both the target set and the library change."),
    # abstract: field-complete is not evidence-complete
    ("attaches a condition marker and a complete provenance field set to each candidate",
     "attaches a condition marker and a field-complete provenance record to each candidate; field "
     "completeness does not imply that condition evidence exists"),
    # multi-step: route-found vs usable
    ("A target counts as successful when the search returns at least one route, whether or not that route "
     "passes the usability check.",
     "A target counts as route-found when the search returns at least one route, whether or not that route "
     "passes the usability check."),
    # results: report usable rate directly
    ("Of the 217 targets that succeeded at depth ≤ 3, 207 have at least one route marked usable.",
     "Of the 217 targets that found a route at depth ≤ 3, 207 have at least one route marked usable, a "
     "usable-target rate of 69.0%. At depth ≤ 2 the usable count was not recorded separately."),
    # remove unsupported "harder"
    ("The gap comes from both a smaller template library and a larger, harder target set.",
     "The gap reflects both a smaller template library and a different, larger target set; the two cannot "
     "be separated with the data reported here."),
    # sampling-noise wording
    ("The remaining gaps are sampling noise at n = 500, not a systematic bias.",
     "The remaining gaps are consistent with sampling noise at n = 500; the intervals do not support a "
     "claim of systematic bias."),
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
