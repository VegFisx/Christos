# -*- coding: utf-8 -*-
r"""验证补库补丁是否已导入（**只读**）：PATCH 行数、抽样字段、以及这些名字现在能不能解析。"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\sources")
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from tcm_ro import open_db                                  # noqa: E402
import herb as H                                            # noqa: E402

with open_db() as con:
    cur = con.cursor()
    total = cur.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
    rows = cur.execute(
        "SELECT herb_id, name_cn, latin, use_part FROM herbs "
        "WHERE herb_id LIKE 'PATCH%' ORDER BY herb_id").fetchall()
    print("herbs 总行数 = %d ｜ PATCH 行数 = %d" % (total, len(rows)))
    for r in rows[:5]:
        print("   %-10s ｜ %-12s ｜ 拉丁=%s ｜ 部位=%s"
              % (r[0], r[1], (r[2] or "—")[:34], (r[3] or "—")[:12]))
    print()
    for nm in ("南板蓝根", "大皂角", "山银花", "杠板归", "小驳骨"):
        got = H._resolve_herb_ids(cur, nm)
        print("   %-6s → %s" % (nm, [(g[1], g[2]) for g in got] or "（仍对不上）"))
