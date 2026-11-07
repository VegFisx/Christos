# -*- coding: utf-8 -*-
# One-shot: strip the AI tells introduced by the later sections.
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
    ("Four optimizations were attempted against the 33-minute full run and none changed the "
     "outcome, which is itself the measurement.",
     "Four optimizations were attempted against the 33-minute full run. None changed the "
     "result."),
    ("Closing the annotation gap needs infrastructure rather than a better model: a predicted "
     "target profile for natural-product scaffolds, or a structure-to-MeSH and "
     "structure-to-RxNorm crosswalk so that a novel product can reach existing toxicity and "
     "adverse-event tables. Neither exists today. Both are data-engineering problems and both "
     "are tractable.",
     "Closing the annotation gap needs infrastructure: either predicted target profiles for "
     "natural-product scaffolds, or structure-to-MeSH and structure-to-RxNorm crosswalks so "
     "that a novel product can reach the existing toxicity and adverse-event tables. Neither "
     "crosswalk exists, and building one is data engineering."),
    ("The current build should not be described as supporting botanical-name lookup for "
     "common Chinese herbs.",
     "The current build does not support botanical-name lookup for common Chinese herbs."),
    ("The audit is a script in the repository (`tools/audit_provenance_completeness.py`) that "
     "reruns on any ledger. Its purpose is to keep the provenance claim checkable rather than "
     "asserted.",
     "The audit is a script in the repository (`tools/audit_provenance_completeness.py`) that "
     "reruns on any ledger, so the provenance claim can be checked instead of taken on trust."),
    ("Products scale with pairs and time scales with pairs, with no efficiency cliff in "
     "between. The pair budget therefore trades waiting time for coverage; it is not a "
     "quality threshold.",
     "Products and time both grow with the pair count. The pair budget trades waiting time for "
     "coverage and is not a quality threshold."),
    ("The fields are always filled. The evidence behind the condition field usually is not.",
     "Every field is filled. What sits behind the condition field usually is not."),
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
