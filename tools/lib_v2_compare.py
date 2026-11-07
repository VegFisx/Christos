# -*- coding: utf-8 -*-
r"""L1 重聚类对照：老库（3,228）vs 全量重聚类库（v2）——大小 / 交并 / 频次结构。"""
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
OLD = STAGE / "reports" / "retro_templates_clustered.jsonl"


def load(p):
    out = {}
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            out[r["template"]] = int(r.get("freq") or 0)
    return out


def main() -> int:
    v2_path = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        STAGE / "reports" / "paper" / "data" / "lib_full_v2.jsonl"
    old, new = load(OLD), load(v2_path)
    inter = set(old) & set(new)
    print("老库 %d · v2 %d · 交集 %d（老库保留 %.0f%%）· 老独有 %d · v2 新增 %d"
          % (len(old), len(new), len(inter), 100.0 * len(inter) / max(1, len(old)),
             len(set(old) - set(new)), len(set(new) - set(old))))
    import statistics as st
    if new:
        fr = sorted(new.values())
        print("v2 频次：中位 %d · p90 %d · 最大 %d（老库中位 %d）"
              % (st.median(fr), fr[int(0.9 * len(fr))], fr[-1], st.median(sorted(old.values()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
