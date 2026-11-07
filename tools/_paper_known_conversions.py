# -*- coding: utf-8 -*-
# One-shot: insert the known-conversion check into the manuscript.
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
    "### Known conversions",
    "",
    "Five conversions documented in the TCM literature were used as a qualitative "
    "reachability check. Each substrate was run alone under the decoction condition "
    "profile for up to three rounds, and the ledger was searched for the documented "
    "product.",
    "",
    "| Conversion | Rule | Round | Candidates | Time |",
    "|---|---|---:|---:|---:|",
    "| Glycyrrhizic acid to glycyrrhetinic acid | hydrolysis_glycoside_001 | 1 | 5,510 | 56 s |",
    "| Ginsenoside Rb1 to Rg3 | hydrolysis_glycoside_001 | 1 | 11,658 | 193 s |",
    "| Aconitine to benzoylaconine | hydrolysis_ester_001 | 1 | 642 | 6 s |",
    "| Benzoylaconine to aconine | hydrolysis_ester_001 | 1 | 814 | 7 s |",
    "| Rutin to quercetin | hydrolysis_glycoside_001 | 1 | 5,685 | 96 s |",
    "",
    "All five products appear in the first round, each produced by the chemically "
    "expected rule: glycoside hydrolysis for the glycosides, ester hydrolysis for the "
    "two diterpenoid alkaloids. The pipeline can therefore reach documented decoction "
    "chemistry. It does not follow that it surfaces the right product, because the "
    "system does not rank at all.",
    "",
    "The candidate counts are the practical limitation. To find the documented product "
    "a researcher has to inspect between 642 and 11,658 entries. A filter layer — mass "
    "balance, condition window, or literature priors — is the obvious next step and "
    "lies outside this paper.",
    "",
])

ANCHOR = "### Herb resolution audit"

ABSTRACT_OLD = ("A field-level audit of a 573-entry herbal run found all nine provenance field "
                "groups present in every entry, but substantive condition rationale in only 1.2% "
                "of them.")
ABSTRACT_NEW = (ABSTRACT_OLD + " Five conversions documented in the TCM literature, covering "
                "glycoside and ester hydrolysis, were all reachable in the first round.")

LIM_OLD = ("9. **The Latin-name path depends on an overloaded field.**")
LIM_NEW = ("9. **Reaching a product is not surfacing it.** All five documented conversions were "
           "found, but each run returned between 642 and 11,658 candidates and the system does "
           "not rank them.\n"
           "10. **The Latin-name path depends on an overloaded field.**")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("anchor=%d abstract=%d lim=%d"
          % (s.count(ANCHOR), s.count(ABSTRACT_OLD), s.count(LIM_OLD)))
    s = s.replace(ANCHOR, SECTION + ANCHOR, 1)
    s = s.replace(ABSTRACT_OLD, ABSTRACT_NEW, 1)
    s = s.replace(LIM_OLD, LIM_NEW, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
