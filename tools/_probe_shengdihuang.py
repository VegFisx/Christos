# -*- coding: utf-8 -*-
r"""一次性探针：『生地黄』这类名字在 HERB 库里到底怎么摆的？"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from tcm_ro import open_db                                  # noqa: E402

KEYS = ("生地黄", "生地", "鲜地黄", "干地黄", "熟地黄", "地黄", "生首乌", "制首乌")

with open_db() as c:
    cur = c.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(herbs)").fetchall()]
    print("herbs 列：", cols)
    print()
    for kw in KEYS:
        n = cur.execute("SELECT COUNT(*) FROM herbs WHERE name_cn = ?", (kw,)).fetchone()[0]
        a = cur.execute("SELECT COUNT(*) FROM herbs WHERE alias LIKE ?",
                        ("%" + kw + "%",)).fetchone()[0]
        print("  %-6s 本名命中=%d ｜ alias 里含它=%d" % (kw, n, a))
    print()
    print("名字里带『地黄』或 alias 带『生地』的行：")
    rows = cur.execute("SELECT name_cn, alias FROM herbs WHERE name_cn LIKE '%地黄%' "
                       "OR name_cn LIKE '%生地%' OR alias LIKE '%生地%'").fetchall()
    for nm, al in rows[:15]:
        print("   %-10s ｜ alias=%s" % (nm, (str(al) or "")[:90]))
