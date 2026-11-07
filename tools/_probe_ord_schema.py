# -*- coding: utf-8 -*-
r"""一次性探针（用 **venv 3.12 + libs** 跑）：ORD parquet 的结构是什么？"""
from __future__ import annotations

import sys

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\libs")
import duckdb                                              # noqa: E402

PQ = (r"D:\ProgramData\DSHNS\chemreact-staging\ord-data\data\11"
      r"\ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet")
con = duckdb.connect(":memory:")
cols = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [PQ]).fetchall()
print("列数", len(cols))
for c in cols:
    print("  %-24s %s" % (c[0], c[1][:70]))
n = con.execute("SELECT COUNT(*) FROM read_parquet(?)", [PQ]).fetchone()[0]
print("行数", n)
