# -*- coding: utf-8 -*-
"""一次性探针（只读）：药典组成里没对上的药材名，库里的实际情况是什么。"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TCM = "file:D:/TCMAI/tcm.db?mode=ro"
WANT = ["熟地黄", "萸肉", "山茱萸", "泽泻", "茯苓", "水牛角浓缩粉", "水牛角",
        "半夏", "生半夏", "甘草浸膏", "广藿香油", "紫苏叶油", "人工麝香", "麝香",
        "淡竹叶", "桂枝", "赤芍", "牡丹皮", "冰片", "三七", "丹参"]


def main() -> None:
    c = sqlite3.connect(TCM, uri=True)
    for w in WANT:
        r = c.execute("SELECT herb_id, name_cn FROM herbs WHERE name_cn=?",
                      (w,)).fetchone()
        al = c.execute("SELECT name_cn FROM herbs WHERE alias LIKE ? LIMIT 3",
                       ("%" + w + "%",)).fetchall()
        print("%-12s 正名命中=%-22s 出现在别名里的=%s"
              % (w, (r[1] if r else "—"), [x[0] for x in al]))
    print()
    print("别名表里含『萸肉』的行：")
    for hid, cn, al in c.execute("SELECT herb_id,name_cn,alias FROM herbs "
                                 "WHERE alias LIKE '%萸肉%' LIMIT 5"):
        print("   ", hid, cn, "|", str(al)[:60])
    c.close()


if __name__ == "__main__":
    main()
