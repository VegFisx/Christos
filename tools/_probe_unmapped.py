# -*- coding: utf-8 -*-
r"""列出药材行里未映射的成分名（按频次）——扩名表的工作清单。"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

D = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\chp_markers")


def main() -> int:
    src = next(iter(sorted(D.glob("chp*_linked.csv"))), None)
    if src is None:
        print("目录里没有 chp*_linked.csv：%s" % D)
        return 2
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    un = [r for r in rows if r["entry_type"] in ("药材", "提取物")
          and r["kind"] == "compound" and not r["db_hits"] and r["name"]
          and r["link_via"] not in ("skip-noise", "aggregate(不连库)")]
    names = collections.Counter(r["name"] for r in un)
    print("未映射 compound 行 %d · 不同名称 %d" % (len(un), len(names)))
    first = {}
    for r in un:
        first.setdefault(r["name"], (r["herb"], r["value"]))
    for n, cnt in names.most_common(60):
        h, v = first[n]
        print("%-24s | x%-3d | %-6s %s%%" % (n[:24], cnt, h, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
