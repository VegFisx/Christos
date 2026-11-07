# -*- coding: utf-8 -*-
# One-shot: apply the fourth-round reviewer fixes to the English draft.
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
    # 1. both reverse libraries are filtered
    ("This is the stricter of the two options. The same filter is applied to the reverse-direction library.",
     "This is the stricter of the two options. Both reverse-direction libraries used in the results are "
     "filtered the same way. They differ in size because they were mined from different template "
     "sources: 79,184 templates for the 5,002-target subset and 3,065 for the full 50,016 targets."),
    # 2. target provenance for reverse and multi-step
    ("A target is a hit if at least one disconnection produces a precursor set equal to the recorded "
     "reactant set after atom-map removal.",
     "A target is a hit if at least one disconnection produces a precursor set equal to the recorded "
     "reactant set after atom-map removal. The 5,002 and 300 target sets are drawn from ORD rather than "
     "USPTO-50k: products with molecular weight at most 500, a single component and no salt form, taken "
     "from an offset of 200,000 rows in the ORD parquet and deduplicated."),
    # 3. selected-config wording no longer implies prefilter gain
    ("The selected configuration uses a support-filtered pool of roughly 20,000 templates, a per-pair "
     "cap of 32, and the compatibility prefilter.",
     "The selected configuration uses a support-filtered pool of roughly 20,000 templates and a per-pair "
     "cap of 32. The compatibility prefilter stays enabled in the pipeline; the ablation below shows it "
     "adds nothing measurable on the test sample."),
    # 4. ablation gap is sampling noise
    ("The sample figures of 41.60% and 75.80% sit next to those equal-weight values.",
     "The sample figures of 41.60% and 75.80% sit next to those equal-weight values. Their Wilson "
     "intervals are 37.36–45.97% and 71.86–79.35%, so both equal-weight values fall inside the "
     "intervals. The remaining gaps are sampling noise at n = 500, not a systematic bias."),
    # 5. condition audit CI
    ("Condition rationale is substantive in 7 entries (1.2%);",
     "Condition rationale is substantive in 7 entries (1.2%, Wilson 95% CI 0.59–2.50%);"),
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
