# -*- coding: utf-8 -*-
r"""一次性：老规格 parquet（带 reaction 列）还在不在？

在 -> 直接读它，省掉 28 ms/条的模板归类（可省 28 分钟）。
不在 -> 只能老老实实归类。
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
ORD = STAGE / "ord-data" / "data"
print("ord-data/data 存在:", ORD.exists())
if ORD.exists():
    pq = sorted(ORD.rglob("*.parquet"))
    print(f"parquet 文件 {len(pq)} 个")
    big = [p for p in pq if "1158e351" in p.name]
    print("含 1158e351 的大文件:", [p.name for p in big])
    for p in pq[:3]:
        print(f"   {p.name}  {p.stat().st_size/1024**2:.1f} MB")
