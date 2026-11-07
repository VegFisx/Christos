# -*- coding: utf-8 -*-
# One-shot: sixth-round fixes for the English draft.
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
    # 1. abstract: qualify multi-step
    ("Multi-step planning reaches 47.67% success at depth ≤ 2 and 72.33% at depth ≤ 3 on 300 targets.",
     "Multi-step planning reaches 47.67% success at depth ≤ 2 and 72.33% at depth ≤ 3 on 300 ORD "
     "targets; unlike the reverse figures, these have not been target-level filtered."),
    # 2. conclusions: same qualification
    ("and multi-step planning reaches 47.67% and 72.33% at depth ≤ 2 and ≤ 3.",
     "and multi-step planning reaches 47.67% and 72.33% at depth ≤ 2 and ≤ 3 on a 300-target ORD set "
     "that has not been target-level filtered."),
    # 3. alias count correction
    ("Exact Chinese names and aliases resolved in every case, with one ambiguous result in each group.",
     "Exact Chinese names resolved in all 20 cases. Aliases resolved in 9 of 10: 寸冬 returned nothing."),
    # 4. negative group wording
    ("Of the ten strings that should not resolve, nine returned nothing. The single character 甘 "
     "returned 40 candidates, the substring cap, because it matches many herb names.",
     "Of the ten strings that should not resolve, nine returned nothing. The single character 甘 returned "
     "40 candidates, the substring cap, because it matches many herb names. That one is a false return, "
     "not a resolution."),
    # 5. Latin scope limitation
    ("The audit script is in the repository (`tools/audit_herb_resolution.py`) and the case list can be "
     "extended.",
     "The 25 table-sourced binomials are the easy case. A user typing the botanical name of a common herb "
     "is represented by a single case here, Glycyrrhiza uralensis, and it failed. The current build should "
     "not be described as supporting botanical-name lookup for common Chinese herbs.\n\n"
     "The audit script is in the repository (`tools/audit_herb_resolution.py`) and the case list can be "
     "extended."),
    # 6. table note defining ambiguous
    ("| Non-herb string | 10 | 1 | 9 | 1 |",
     "| Non-herb string | 10 | 1 | 9 | 1 |\n\n"
     "Ambiguous counts entries that returned more than one candidate; it is a subset of resolved, not a "
     "separate outcome. In the non-herb row the single resolved entry is a false return, not a correct "
     "resolution."),
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
