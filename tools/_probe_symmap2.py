# -*- coding: utf-8 -*-
"""一次性探针：SymMap SMHB 的 Alias 列 + HERBDB_ID 对接成色。"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

XLS = Path(r"D:\ProgramData\DSHNS\chemreact-staging\data\symmap\SymMap v2.0_SMHB file.xlsx")


def main() -> None:
    import openpyxl
    wb = openpyxl.load_workbook(XLS, read_only=True, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = [str(x) for x in rows[0]]
    ia, ih = hdr.index("Alias"), hdr.index("HERBDB_ID")
    ic = hdr.index("Chinese_name")
    wb.close()
    recs = []
    for r in rows[1:]:
        if not r or not r[ic]:
            continue
        al = str(r[ia] or "").strip()
        al = "" if al in ("None", "nan") else al
        recs.append({"herb": str(r[ic]).strip(),
                     "herbdb": str(r[ih] or "").strip(),
                     "alias_raw": al})
    print("SymMap 药材 = %d，其中 Alias 非空 = %d（%.1f%%）"
          % (len(recs), sum(1 for x in recs if x["alias_raw"]),
             100.0 * sum(1 for x in recs if x["alias_raw"]) / len(recs)))
    print("别名原文样例：")
    for x in recs:
        if x["alias_raw"]:
            print("   %-8s [%s] %s" % (x["herb"], x["herbdb"], x["alias_raw"][:90]))
        if x["herb"] in ("甘草", "人参"):
            pass
    # 与 tcm.db 按 herb_id 对齐
    c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
    ids = {r[0]: r[1] for r in c.execute("SELECT herb_id, name_cn FROM herbs")}
    c.close()
    ok = [x for x in recs if x["herbdb"] in ids]
    print("\nHERBDB_ID 能在 tcm.db 命中 = %d / %d（%.1f%%）"
          % (len(ok), len(recs), 100.0 * len(ok) / len(recs)))
    # ID 命中但中文名不一致的
    diff = [(x["herb"], ids[x["herbdb"]]) for x in ok if ids[x["herbdb"]] != x["herb"]]
    print("  ID 对上但中文名不同 = %d，样例 %s" % (len(diff), diff[:6]))
    # 展开别名
    sep = Counter()
    pairs = {}
    for x in recs:
        if not x["alias_raw"]:
            continue
        for s in ("；", ";", "，", ",", "、", "/", "|"):
            if s in x["alias_raw"]:
                sep[s] += 1
        for a in re.split(r"[；;，,、/|]", x["alias_raw"]):
            a = a.strip()
            if a and a != x["herb"]:
                pairs.setdefault(a, set()).add(x["herb"])
    print("  分隔符出现：", sep.most_common())
    print("  展开后别名条数（去重）= %d" % len(pairs))
    print("  样例：", list(pairs.items())[:8])
    print("  一个别名指向多个药材的 = %d（这些必须保留成多候选）"
          % sum(1 for v in pairs.values() if len(v) > 1))


if __name__ == "__main__":
    main()
