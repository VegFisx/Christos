# -*- coding: utf-8 -*-
r"""把两批 H2 判定合并成 `data\h2_verdicts_all.json`（n=300），并打印合计。"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
SRC = [STAGE / "data" / "h2_verdicts_b1.json", STAGE / "data" / "h2_verdicts_b2.json"]
OUT = STAGE / "data" / "h2_verdicts_all.json"


def main() -> int:
    rows = []
    for p in SRC:
        rows += json.loads(p.read_text(encoding="utf-8"))
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 90)
    print("H2 合并（n=%d）" % len(rows))
    print("=" * 90)
    for b in sorted({r["批次"] for r in rows}):
        sub = [r for r in rows if r["批次"] == b]
        c = Counter(r["判定"] for r in sub)
        print("  第 %d 批 n=%3d：命中 %2d（%.0f%%）｜部分命中 %2d ｜查无 %2d"
              % (b, len(sub), c["命中"], 100.0 * c["命中"] / len(sub),
                 c["部分命中"], c["查无"]))
    c = Counter(r["判定"] for r in rows)
    print("  合计   n=%3d：命中 %2d（%.1f%%）｜部分命中 %2d ｜查无 %2d（%.1f%%）"
          % (len(rows), c["命中"], 100.0 * c["命中"] / len(rows),
             c["部分命中"], c["查无"], 100.0 * c["查无"] / len(rows)))
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
