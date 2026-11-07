# -*- coding: utf-8 -*-
# 一次性：数一下本地 ORD parquet 有多少行（决定出处还原是否顺手带上 reaction_id）
import sys
from pathlib import Path

_STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (_STAGE / "libs",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BIG = Path(r"D:\ProgramData\DSHNS\chemreact-staging\ord-data\data\11"
           r"\ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet")
con = duckdb.connect()
print("rows:", con.execute(f"SELECT COUNT(*) FROM read_parquet('{BIG.as_posix()}')").fetchone()[0])
print("cols:", [d[0] for d in con.execute(
    f"DESCRIBE SELECT * FROM read_parquet('{BIG.as_posix()}')").fetchall()])
