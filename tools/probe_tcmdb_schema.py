# -*- coding: utf-8 -*-
"""一次性：打印 tcm.db 的 compounds 表结构（只看形状，不看内容）。"""
import sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
sys.path.insert(0, r"D:\TCMAI\src")
from tcm_ro import use_readonly; use_readonly()
from db_utils import open_db

with open_db() as c:
    cur = c.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("tables:", [r[0] for r in cur.fetchall()])
    cur.execute("PRAGMA table_info(compounds)")
    for r in cur.fetchall():
        print(f"   {r[1]:<24} {r[2]}")
    cur.execute("SELECT count(*) FROM compounds")
    print("compounds rows:", cur.fetchone()[0])
