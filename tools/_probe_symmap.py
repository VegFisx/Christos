# -*- coding: utf-8 -*-
"""一次性探针：SymMap SMHB（药材表）的结构，找别名字段。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

D = Path(r"D:\ProgramData\DSHNS\chemreact-staging\data\symmap")


def main() -> None:
    try:
        import openpyxl
    except Exception as ex:                                # noqa: BLE001
        print("没有 openpyxl：%s" % ex)
        return
    for p in sorted(D.glob("*.xlsx")):
        print("=" * 90)
        print(p.name)
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        print("  工作表：", wb.sheetnames)
        for sn in wb.sheetnames[:2]:
            ws = wb[sn]
            print("  [%s] %d 行 × %d 列" % (sn, ws.max_row, ws.max_column))
            rows = list(ws.iter_rows(values_only=True))
            print("     全部列名：", [str(x)[:22] for x in rows[0]])
            for i, row in enumerate(rows[:3]):
                print("     r%d: %s" % (i + 1, [str(x)[:24] for x in row]))
            if "key" in p.name:
                from collections import Counter
                fld = Counter(str(r[1]) for r in rows[1:] if r and r[1])
                print("     字段出现次数：", fld.most_common(14))
                for f in fld:
                    if any(k in f.lower() for k in ("alia", "synon", "other", "common")):
                        ex = [r for r in rows[1:] if str(r[1]) == f][:5]
                        print("     ★ 疑似别名字段 %s 样例：%s" % (f, [(r[0], r[2]) for r in ex]))
        wb.close()


if __name__ == "__main__":
    main()
