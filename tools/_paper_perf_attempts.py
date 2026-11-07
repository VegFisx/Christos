# -*- coding: utf-8 -*-
# One-shot: record what performance work was tried and what it did not fix.
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
    "### What did not help",
    "",
    "Four optimizations were attempted against the 33-minute full run and none changed the "
    "outcome, which is itself the measurement.",
    "",
    "Caching single-substrate template results across batches changed nothing. The 72 "
    "seconds spent on 1,000 pairs is dominated by 11,000 calls to RDKit's `RunReactants`, "
    "about 6.5 ms each; the single-substrate path is a small share.",
    "",
    "Enumerating pair indices directly, rather than materialising the full 58,311-tuple "
    "list before slicing, also changed nothing.",
    "",
    "Streaming products to disk in 200-pair batches lowered peak memory from 1.8 GB to a "
    "flat profile, but ran 60% slower than 2,000-pair slices because per-batch setup "
    "dominates at that granularity.",
    "",
    "Four-process parallelism works in principle: slices are independent, and the first "
    "four completed with product counts identical to the serial run. It fails on memory. "
    "Each worker holds about 1.7 GB of product objects, so four workers exhaust a 16 GB "
    "machine and two are killed without an error trace. The bottleneck is the per-product "
    "object footprint, not the template library: loading all 82,000 templates costs about "
    "37 MB.",
    "",
    "Breaking the ceiling would require changing what a product object carries, deferring "
    "provenance lookups until the row is written. That is an engine-level change and is "
    "left open.",
    "",
])

ANCHOR = "## Discussion"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor=%d" % n)
    if n:
        s = s.replace(ANCHOR, SECTION + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
