# -*- coding: utf-8 -*-
"""一次性：看已有的 5000 条 sample 里有什么列（是否含 solvent/temperature）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
import duckdb  # noqa: E402

D = STAGE / "reports" / "ord_condition_dataset"
p = D / "sample_limit5000_seed20261013.parquet"
con = duckdb.connect()
cols = [c[0] for c in con.execute(
    f"DESCRIBE SELECT * FROM read_parquet('{p.as_posix()}')").fetchall()]
print("sample 列 =", cols)
print("行数 =", con.execute(
    f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0])
st = D / "sample_limit5000_seed20261013.stats.json"
if st.exists():
    s = json.loads(st.read_text(encoding="utf-8"))
    print("stats keys =", list(s.keys()))
    for k in ("n_records", "columns", "note", "sampling"):
        if k in s:
            print(f"   {k} = {str(s[k])[:160]}")
