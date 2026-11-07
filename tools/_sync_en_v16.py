# -*- coding: utf-8 -*-
# One-shot: align conclusion with the abstract's scope, add headline context,
# and correct the herb compound count in the abstract.
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
    # abstract: herb compound count
    ("31,646 herb compounds, 269,105 COCONUT compounds",
     "31,646 herb compound records (25,486 distinct SMILES), 269,105 COCONUT compounds"),
    # abstract: headline context
    ("On a leak-controlled USPTO-50k benchmark, the selected forward configuration reaches 82.32% "
     "single-step recall on 50,016 reactions (41,173 hits; Wilson 95% CI 81.98–82.65%), against 55.43% "
     "for the baseline configuration.",
     "On a leak-controlled USPTO-50k benchmark, the selected forward configuration reaches 82.32% "
     "single-step recall on 50,016 reactions (41,173 hits; Wilson 95% CI 81.98–82.65%), against 55.43% "
     "for the baseline configuration. That figure comes at a per-pair cap of 32 with 21.2 candidates per "
     "reaction on average, so it is a lower bound on uncapped recall; weighting every reaction class "
     "equally gives 75.22%. No external system was run on this benchmark, and the paper makes no claim of "
     "state-of-the-art performance."),
    # conclusion: scope
    ("Christos provides a provenance-aware, read-only workflow for reaction prediction in natural-product "
     "and TCM research,",
     "Christos provides a provenance-aware, read-only workflow for reaction enumeration and provenance in "
     "herbal and natural-product data, with prediction performance benchmarked only on USPTO-50k and ORD,"),
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
