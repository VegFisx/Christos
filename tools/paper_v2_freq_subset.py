# -*- coding: utf-8 -*-
r"""按频次门槛生成 v2 基准库子集（生产选型对照用）。

用法:
  python tools\paper_v2_freq_subset.py [min_freq] [src] [dst]

默认：min_freq=10；src=reports/paper/data/lib_uspto50k_excl_v2.jsonl；
      dst=reports/paper/data/lib_uspto50k_excl_v2_freq<min_freq>.jsonl
输出：dst 的条数 + 与源库的频次分布摘要。只读源库，重跑会覆写 dst（幂等）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
DEF_SRC = STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl_v2.jsonl"


def main() -> int:
    min_freq = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    src = Path(sys.argv[2]) if len(sys.argv) > 2 else DEF_SRC
    dst = Path(sys.argv[3]) if len(sys.argv) > 3 else \
        src.parent / ("%s_freq%d.jsonl" % (src.stem, min_freq))
    n_in = n_out = 0
    with open(dst, "w", encoding="utf-8") as fo:
        for line in open(src, encoding="utf-8"):
            if not line.strip():
                continue
            n_in += 1
            d = json.loads(line)
            if int(d.get("freq") or 0) >= min_freq:
                fo.write(line)
                n_out += 1
    print("源 %s（%d 条）-> %s（freq>=%d：%d 条）" % (src.name, n_in, dst, min_freq, n_out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
