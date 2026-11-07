# -*- coding: utf-8 -*-
"""一次性：分片里 reaction_class 列长什么样、覆盖率多少（只回答这一个问题）。"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
import duckdb  # noqa: E402

SH = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
con = duckdb.connect()
con.execute("SET enable_progress_bar=false")
rows = con.execute(
    f"SELECT reaction_class, solvent_names FROM read_parquet('{SH}') "
    f"USING SAMPLE 40000 ROWS (reservoir, 20261013)").fetchall()
print(f"抽样 {len(rows):,} 条")
c = Counter(str(r[0]) for r in rows)
n_empty = c.get("", 0) + c.get("None", 0) + c.get("nan", 0)
print(f"reaction_class 非空 {len(rows)-n_empty:,} = {(len(rows)-n_empty)/len(rows):.1%}")
print(f"不同取值 {len(c)} 个，前 20：")
for k, v in c.most_common(20):
    print(f"   {v:>7,}  {k[:70]}")
