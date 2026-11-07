# -*- coding: utf-8 -*-
# One-shot: add the two-stage filter, applications and outlook to the paper.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

FILTER = "\n".join([
    "### Two-stage filtering",
    "",
    "The 3,210 candidates from the Sijunzi run were reduced in two steps. First, only "
    "rules from the TCM rulebook were kept, which removed the general organic-synthesis "
    "templates mined from ORD; 3,210 fell to 1,114. Second, each product's InChIKey was "
    "checked against the 31,646 compounds in the herb database. Six products were already "
    "known herbal constituents and 1,108 were not.",
    "",
    "The six known products arise from four ester-hydrolysis and two glycoside-hydrolysis "
    "events. The overall compression is 99.8%. A reader is left with six compounds that "
    "have a literature identity, rather than 3,210 structures to inspect by hand.",
    "",
    "The filter is not a ranking and carries no confidence score. It applies two "
    "explicit criteria — rule provenance and membership in the compound table — and a "
    "product either passes both or does not. The 1,108 products outside the table remain "
    "available under a separate flag; they are candidates for novel constituents, not "
    "errors.",
    "",
])

APPS = "\n".join([
    "### Applications",
    "",
    "Four uses follow directly from what the system now does.",
    "",
    "Decoction product prediction. Given a herb combination, the pipeline returns the "
    "products that can form only after the herbs are combined and heated. On the Sijunzi "
    "combination this yields six literature-identifiable constituents from 3,210 raw "
    "candidates after filtering.",
    "",
    "Processing-detoxification mechanism. The two-step hydrolysis of aconitine to "
    "benzoylaconine and then to aconine is reproduced in the first round. This is the "
    "central chemistry of Aconitum processing.",
    "",
    "Quality-marker screening. Products that appear after decoction but are absent from "
    "the raw herbs are candidate markers for distinguishing decocted material from "
    "powdered herb.",
    "",
    "Compatibility chemistry. A product whose two precursors come from different herbs "
    "is direct evidence that the combination, and not either herb alone, produced it.",
    "",
    "### Outlook",
    "",
    "Three extensions are immediate. The TCM rulebook holds 64 rules; a systematic "
    "literature mining effort could take it to several hundred, which is the single "
    "largest lever on coverage. The filter currently uses rule provenance and compound "
    "identity; mass balance, condition windows and literature priors would tighten it "
    "further. And every prediction in this paper is unverified against experiment, which "
    "is the step that would turn a reachability check into an accuracy claim.",
    "",
])

ANCHOR = "## Discussion"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("anchor=%d" % s.count(ANCHOR))
    s = s.replace(ANCHOR, FILTER + ANCHOR, 1)
    # Applications/Outlook go at the end of the Discussion, before Limitations.
    lim = "## Limitations"
    print("lim=%d" % s.count(lim))
    s = s.replace(lim, APPS + lim, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
