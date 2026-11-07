# -*- coding: utf-8 -*-
r"""从 L1 全量挖矿分片构建【正向】模板库（翻转 + 支持计数）。

原理：分片里每行 = 一条 ORD 记录的 {rx（带映射反应）, template（产物>>前体）}。
把 template 两侧翻面即得**同一条反应的正向模板**（前体>>产物）——与既有
mined_forward_templates*（60k 抽样版）同方向；本脚本把覆盖推到全量 1.77M。

输出: reports/mined_forward_templates_full.jsonl
      {"template": "前体>>产物", "support": n, "src": "ord_shards_full"}
只读分片；不发任何网络请求。
"""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
SHARDS = STAGE / "reports" / "ord_shards_full"
OUT = STAGE / "reports" / "mined_forward_templates_full.jsonl"


def main() -> int:
    t0 = time.time()
    files = sorted(SHARDS.glob("shard_*.jsonl"))
    print("分片 %d 个" % len(files), flush=True)
    cnt = collections.Counter()
    n_rows = n_bad = 0
    for k, fp in enumerate(files, 1):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n_rows += 1
                try:
                    t = json.loads(line).get("template") or ""
                except Exception:
                    n_bad += 1
                    continue
                if ">>" not in t:
                    n_bad += 1
                    continue
                a, b = t.split(">>", 1)
                cnt[b + ">>" + a] += 1
        if k % 50 == 0:
            print("  ... %d/%d 片 · 累计 %d 行 · 唯一模板 %d · %.0fs"
                  % (k, len(files), n_rows, len(cnt), time.time() - t0), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for t, n in cnt.most_common():
            f.write(json.dumps({"template": t, "support": n, "src": "ord_shards_full"},
                               ensure_ascii=False) + "\n")
    n5 = sum(1 for _, n in cnt.items() if n >= 5)
    n10 = sum(1 for _, n in cnt.items() if n >= 10)
    print("完成：读入 %d 行（坏行 %d）· 唯一正向模板 %d（support>=5: %d · >=10: %d）"
          % (n_rows, n_bad, len(cnt), n5, n10))
    print("输出 -> %s（%.1f MB · %.0fs）"
          % (OUT, OUT.stat().st_size / 1048576, time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
