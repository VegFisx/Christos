# -*- coding: utf-8 -*-
# One-shot: fix the InChIKey explanation, cap-64 wording and Latin sentence.
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
    ("The two counts differ because some distinct SMILES strings map to the same InChIKey.",
     "The two figures are computed over different record sets: every record carries a SMILES, but only "
     "30,964 carry an InChIKey, so the distinct-key count is not directly comparable with the "
     "distinct-SMILES count."),
    ("Raising the cap from 32 to 64 changes neither recall nor candidate count on this sample,",
     "Raising the cap from 32 to 64 leaves recall unchanged and moves the mean candidate count by 0.2 on "
     "this sample,"),
    ("Glycyrrhiza uralensis resolved to 甘草节, a node of the licorice root, rather than to 甘草.",
     "Glycyrrhiza uralensis resolved to 甘草节 (a node of the licorice root), rather than to 甘草."),
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
