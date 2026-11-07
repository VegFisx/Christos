# -*- coding: utf-8 -*-
"""一次性探针（只读）：NTU《中文药名同义词表》Excel 的结构与成色。"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

XLS = Path(r"D:\TCMAI\data\ChineseDrugEthnonymsSynonymyTable.xlsx")


def main() -> None:
    import openpyxl
    wb = openpyxl.load_workbook(XLS, read_only=True, data_only=True)
    print("工作表：", wb.sheetnames)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    print("总行 = %d（含表头）" % len(rows))
    print("表头：", [str(x) for x in rows[0]])
    print("前 5 行：")
    for r in rows[1:6]:
        print("   ", [str(x)[:34] for x in r])
    wb.close()
    # 统计
    alt_to_primary = {}
    primaries = set()
    dsrc = Counter()
    n_multi = 0
    for r in rows[1:]:
        if len(r) < 4 or not r[1] or not r[3]:
            continue
        primary = str(r[1]).strip()
        alt = str(r[3]).strip()
        primaries.add(primary)
        dsrc[str(r[2])[:40]] += 1
        alt_to_primary.setdefault(alt, set()).add(primary)
    print()
    print("规范名（PrimaryDrugName）去重 = %d" % len(primaries))
    print("别名（AlternateName）去重 = %d" % len(alt_to_primary))
    print("★ 一个别名指向多个规范名的 = %d（这些现在被脚本'自动选一个'丢掉了）"
          % sum(1 for v in alt_to_primary.values() if len(v) > 1))
    print("辞典来源分布 Top 10：")
    for k, n in dsrc.most_common(10):
        print("   %-42s %d" % (k, n))
    ex = [(k, sorted(v)) for k, v in alt_to_primary.items() if len(v) > 1][:8]
    print("多候选样例：", ex)


if __name__ == "__main__":
    main()
