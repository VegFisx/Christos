# -*- coding: utf-8 -*-
r"""探针：ORD 条件表里的【试剂/agents】信息到底有多少可用？

背景（第二十四轮）：氧化还原气氛门控净亏，根因是"试剂可得率 0%"——
记录里真正用的 NaBH₄ 不在条件里，门控就把正确的还原当"气氛不允许"杀掉。
本探针回答：`reagent_names` / `reagent_smiles` / `agents_mapped` 这几列**实际填了多少、内容是什么**。
（先打印原始值，再决定怎么解析 —— 纪律要求）
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
# ★ duckdb 在 staging/libs 里（venv 没有）—— 必须在 import 之前加 sys.path（这个坑犯第三次了）
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()

con = duckdb.connect()
print("=" * 100)
print("ORD 条件表：试剂/agents 列可用性")
print("=" * 100)

cols = [r[0] for r in con.execute(
    f"DESCRIBE SELECT * FROM read_parquet('{SHARDS}')").fetchall()]
print(f"  全部列（{len(cols)}）：{cols}")

for c in ("reagent_names", "reagent_smiles", "agents_mapped",
          "solvent_names", "solvent_smiles", "catalyst_names"):
    if c not in cols:
        print(f"\n  {c}: 【不存在】")
        continue
    row = con.execute(f"""
        SELECT count(*) AS n,
               sum(CASE WHEN {c} IS NULL OR {c} = '' THEN 1 ELSE 0 END) AS empty,
               count(DISTINCT {c}) AS nuniq
        FROM read_parquet('{SHARDS}')
    """).fetchone()
    n, empty, nuniq = row
    print(f"\n  {c}: 非空 {n-empty:,}/{n:,} = {(n-empty)/n:.2%}   唯一值 {nuniq:,}")
    rows = con.execute(f"""
        SELECT {c} FROM read_parquet('{SHARDS}')
        WHERE {c} IS NOT NULL AND {c} <> '' LIMIT 5
    """).fetchall()
    for (v,) in rows:
        print(f"      原始: {str(v)[:170]}")
