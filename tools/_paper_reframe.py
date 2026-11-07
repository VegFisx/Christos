# -*- coding: utf-8 -*-
# One-shot: reframe the introduction and conclusion around findings.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

INTRO_OLD = "Christos was built around four requirements:"
INTRO_NEW = (
    "The system described here was built by auditing each layer of the TCM data pipeline "
    "before trusting the layer above it. That audit produced four findings, and each one "
    "changed the design: a curated rule library of 64 entries of which the loader used six, "
    "a condition gate that admitted reduction reactions under an air atmosphere, a "
    "provenance record that was complete in structure but carried substantive condition "
    "evidence in 1.2% of entries, and an identifier column that mixed botanical names with "
    "pharmacopoeial drug names. Section 5 reports each of these with its measurement.\n\n"
    "Christos was therefore built around four requirements:"
)

CONC_OLD_START = "Christos provides a provenance-aware, read-only workflow for reaction enumeration and provenance in herbal and natural-product data,"
CONC_NEW = "\n".join([
    "Christos exists to make reaction prediction auditable, and the audit found more than the "
    "design anticipated.",
    "",
    "The pipeline reaches documented decoction chemistry. Five literature conversions covering "
    "glycoside and ester hydrolysis all appear in the first round, and two-stage filtering "
    "reduces a 3,210-candidate decoction run to six literature-identifiable constituents.",
    "",
    "It also exposed four defects that a system-level claim would have concealed: 58 of 64 "
    "curated rules were never loaded, reduction rules passed an air-only condition gate, "
    "provenance fields were complete while substantive condition evidence was present in 1.2% "
    "of entries, and the Latin-name column held drug names rather than botanical names.",
    "",
    "The benchmark numbers — 82.32% forward recall, and reverse coverage of 94.74% and 79.81% "
    "under two different configurations — describe the engine, not the herbal layer. The herbal "
    "layer is evaluated as input resolution and provenance, and its limitations are listed "
    "beside its results.",
    "",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("intro=%d conc=%d" % (s.count(INTRO_OLD), s.count(CONC_OLD_START)))
    s = s.replace(INTRO_OLD, INTRO_NEW, 1)
    start = s.index(CONC_OLD_START)
    end = s.index("\n\n## Data and code availability", start)
    s = s[:start] + CONC_NEW.rstrip() + s[end:]
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
