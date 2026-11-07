# -*- coding: utf-8 -*-
r"""一次性探针：18 条已确认异名的**目标正名**在 tcm.db 里是否都有？"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from tcm_ro import open_db                                  # noqa: E402

PAIRS = [("桂心", "肉桂"), ("胆星", "胆南星"), ("龟版", "龟甲"), ("芎", "川芎"),
         ("川椒", "花椒"), ("葶苈", "葶苈子"), ("朴消", "朴硝"), ("火消", "硝石"),
         ("杞子", "枸杞子"), ("海蛤", "蛤壳"), ("诃黎勒皮", "诃子"), ("白茯", "茯苓"),
         ("山栀仁", "栀子"), ("牛蒡", "牛蒡子"), ("川楝肉", "川楝子"),
         ("胡桃", "核桃仁"), ("夜明沙", "夜明砂"), ("山萸", "山茱萸")]

with open_db() as con:
    cur = con.cursor()
    have = {r[0] for r in cur.execute("SELECT name_cn FROM herbs")}
    for a, b in PAIRS:
        print("  %-6s → %-6s %s" % (a, b, "✔ 库里有" if b in have else "✘ 库里没有"))
