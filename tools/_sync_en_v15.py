# -*- coding: utf-8 -*-
# One-shot: tighten the title/abstract scope, clarify the leak-filter order.
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
    ("# Christos: a provenance-aware, read-only reaction prediction system for natural-product and "
     "traditional Chinese medicine research",
     "# Christos: a provenance-aware, read-only reaction prediction engine with explicit input resolution "
     "for herbal and natural-product data"),
    ("The 5,002 reverse targets were checked against the template-mining source.",
     "The exclusion runs before template counting: each ORD record is tested against the USPTO-50k product "
     "set, and a matching record never reaches the counter. Templates are built only from records that "
     "pass the test; none are removed afterwards.\n\nThe 5,002 reverse targets were checked against the "
     "template-mining source."),
    ("A field-level audit of a 573-entry herbal run found all nine provenance field groups present in every "
     "entry, but substantive condition rationale in only 1.2% of them.",
     "A field-level audit of a 573-entry herbal run found all nine provenance field groups present in every "
     "entry, but substantive condition rationale in only 1.2% of them.\n\nPrediction performance is "
     "measured on USPTO-50k and ORD only. The herbal component is evaluated as an input-resolution and "
     "provenance layer, not as a reaction-prediction benchmark: no TCM reaction ground truth is available, "
     "and the 573-entry Glycyrrhiza ledger has not been checked against experiment or literature."),
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
