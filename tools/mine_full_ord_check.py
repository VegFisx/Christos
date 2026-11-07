# -*- coding: utf-8 -*-
r"""L1 挖矿完成后的完整性检查：片数 / 记录数 / 成功-失败统计（从片日志汇总）。"""
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
OUT = STAGE / "reports" / "ord_shards_full"


def main() -> int:
    files = sorted(OUT.glob("shard_*.jsonl"))
    logs = sorted(OUT.glob("shard_*.log"))
    n_rec = 0
    for p in files:
        with open(p, encoding="utf-8") as f:
            n_rec += sum(1 for _ in f)
    ok = bad = 0
    stat_tot = Counter()
    anomalies = []
    for p in logs:
        txt = p.read_text(encoding="utf-8", errors="replace").strip()
        parsed = None
        if txt:
            try:
                parsed = json.loads(txt.splitlines()[-1])
            except Exception:
                parsed = None
        if parsed is None:
            bad += 1
            anomalies.append(p.name)
            continue
        ok += 1
        stat_tot.update(parsed.get("stat", {}))
    print("片文件 %d（期望 286）· 抽取记录合计 %d" % (len(files), n_rec))
    print("日志完好 %d · 异常 %d" % (ok, bad))
    if anomalies:
        print("  异常片（前 10）：", anomalies[:10])
    print("日志内统计合计：", dict(stat_tot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
