# -*- coding: utf-8 -*-
# One-shot: state the reconstructed benchmark configuration and its provenance.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
         r"\manuscript-humanized.md")

OLD = ("The baseline configuration is the forward engine's default: default candidate cap, default "
       "template pool, no substrate-compatibility prefilter. The selected configuration uses a "
       "support-filtered pool of roughly 20,000 templates and a per-pair cap of 32. The compatibility "
       "prefilter stays enabled in the pipeline; the ablation below shows it adds nothing measurable on "
       "the test sample.")

NEW = ("The baseline configuration kept the engine default of 8 products per substrate pair, used no "
       "extra template pool, and left the compatibility prefilter off. The selected configuration raised "
       "the cap to 32, added a pool capped at 20,000 templates mined with support at least 10, and turned "
       "the prefilter on.\n\n"
       "The candidate distributions support this reconstruction. The baseline median is 8 and the "
       "selected configuration's 90th percentile is 32, each sitting at its own cap. The benchmark "
       "scripts take their settings from environment variables and the result files record only the "
       "aggregate, so the values above are rebuilt from engine defaults and the changelog rather than "
       "read back from a run manifest. The compatibility prefilter stays enabled in the selected "
       "pipeline, although the ablation below shows it adds nothing measurable on the test sample.")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(OLD)
    print("hits=%d" % n)
    if n:
        s = s.replace(OLD, NEW, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
