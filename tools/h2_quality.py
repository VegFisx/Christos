# -*- coding: utf-8 -*-
r"""H2 · 取证质量盘点：哪些条目的搜索结果**够用来判定**，哪些要补抓。

判据（宽松，只用来决定"要不要补抓"）：
  某条结果里 title+snippet 同时出现 **方名** 和 **组成类词**（组成/配方/处方/方剂/功效/主治）
  → 记为"可用结果"。0 条的条目 = 需要补抓。
"""
from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
NET = STAGE / "reports" / "_h2_net"
KEY = ("组成", "配方", "处方", "方剂", "功效", "主治", "材料", "药材")


def usable(d: dict) -> int:
    nm = d["方名"]
    n = 0
    for r in d.get("results") or []:
        blob = (r.get("title") or "") + " " + (r.get("snippet") or "")
        if nm in blob and any(k in blob for k in KEY):
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--net", default=str(NET))
    ap.add_argument("--refetch-out", default=str(STAGE / "data" / "h2_refetch.json"))
    a = ap.parse_args()
    net = Path(a.net)
    files = sorted(net.glob("[0-9][0-9][0-9]_*.json"))
    weak, good = [], []
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        n = usable(d)
        (good if n else weak).append((d["序号"], d["方名"], d.get("engine_used"), n))
    print("=" * 100)
    print("H2 取证盘点：%d 条已抓 ｜ 有可用结果 %d 条 ｜ 需补抓 %d 条"
          % (len(files), len(good), len(weak)))
    print("=" * 100)
    from collections import Counter
    print("  可用条目的引擎分布：", dict(Counter(g[2] for g in good)))
    print("  需补抓条目的引擎分布：", dict(Counter(w[2] for w in weak)))
    print()
    print("  需补抓清单（序号 方名 原引擎）：")
    for i in range(0, len(weak), 5):
        print("      " + " ｜ ".join("#%03d %s(%s)" % (w[0], w[1][:8], w[2])
                                     for w in weak[i:i + 5]))
    out = Path(a.refetch_out)
    out.write_text(json.dumps({"weak": [w[0] for w in weak]}, ensure_ascii=False),
                   encoding="utf-8")
    print()
    print("  待补抓序号 -> data\\h2_refetch.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
