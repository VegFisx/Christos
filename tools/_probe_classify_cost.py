# -*- coding: utf-8 -*-
"""一次性计时：enumerate_pairs 归类 ORD 记录的**单位成本**（只回答这一个问题）。

输出：每 100 条记录归类耗时（串行/并行各一次），据此决定 build_direction_evidence 抽多少。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402

SHARD = (STAGE / "reports" / "ord_condition_dataset" / "shard_0000.parquet").as_posix()
N = 200

con = duckdb.connect()
rows = con.execute(
    f"SELECT reactants, product FROM read_parquet('{SHARD}') LIMIT {N}").fetchall()
payload = [(str(r[0] or ""), str(r[1] or "")) for r in rows if r[0] and r[1]]
print(f"取 {len(payload)} 条做计时", flush=True)

from smartreact import ReactionEnumerator  # noqa: E402
enum = ReactionEnumerator()

t0 = time.time()
got = list(enum.enumerate_pairs(payload, parallel=False))
d1 = time.time() - t0
names = {getattr(r, "reaction_name", "") for r in got}
print(f"串行：{d1:.2f}s  -> {d1/len(payload)*1000:.1f} ms/条  认出 {len(names)} 个类型", flush=True)

t0 = time.time()
got2 = list(enum.enumerate_pairs(payload, parallel=True))
d2 = time.time() - t0
print(f"并行：{d2:.2f}s  -> {d2/len(payload)*1000:.1f} ms/条  {len(got2)} 组", flush=True)
print(f"推算：60,000 条串行约 {d1/len(payload)*60000/60:.1f} 分钟", flush=True)
print("类型样例：" + ", ".join(sorted(names)[:8]), flush=True)
