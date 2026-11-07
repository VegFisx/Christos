# -*- coding: utf-8 -*-
# One-shot: record the missing downstream-annotation bridge.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

LIM_ANCHOR = "10. **The Latin-name path depends on an overloaded field.**"
LIM_ADD = "\n".join([
    "10. **Downstream risk annotation stops at known compounds.** A predicted product that "
    "is not already in a compound table has no identifier to join against toxicity or "
    "disease records. The ADMET cache joins on InChIKey and covers 2.6% of a decoction run; "
    "CTD joins on chemical names and covers effectively none, because novel structures have "
    "no name to match. On the same pair of formulas the ADMET cache separates a mild "
    "combination from an Aconitum one cleanly — 0 of 84 annotated products above the 90th "
    "percentile of acute toxicity versus 65 of 169 — but only for the minority of products "
    "that prior curation recognised.",
    "11. **The Latin-name path depends on an overloaded field.**",
])

OLD_OUTLOOK = ("Three extensions are immediate.")
NEW_OUTLOOK = "\n".join([
    "Closing the annotation gap needs infrastructure rather than a better model: a predicted "
    "target profile for natural-product scaffolds, or a structure-to-MeSH and "
    "structure-to-RxNorm crosswalk so that a novel product can reach existing toxicity and "
    "adverse-event tables. Neither exists today. Both are data-engineering problems and both "
    "are tractable.",
    "",
    "Three further extensions are immediate.",
])


def main() -> int:
    s = P.read_text(encoding="utf-8")
    print("lim=%d outlook=%d" % (s.count(LIM_ANCHOR), s.count(OLD_OUTLOOK)))
    s = s.replace(LIM_ANCHOR, LIM_ADD, 1)
    s = s.replace(OLD_OUTLOOK, NEW_OUTLOOK, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
