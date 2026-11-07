# -*- coding: utf-8 -*-
r"""阶段C 前置探针：ORD 的 reaction 字段能不能对上 SmartReact 的 37 个类名？

只回答两个问题：
  1. reports/conditions_normalized.json 里的 37 个类名长什么样（这就是门控的 key）
  2. ORD parquet 的 `reaction` 字段有哪些取值、出现频次如何（决定能不能直接路由）
若两者能对上 -> 「自抽模板按类型路由进条件门控」可行；
若对不上 -> 必须先做一层名称映射（这是额外工作，不能假装它不存在）。

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\probe_reaction_class_mapping.py
"""
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
# ★ duckdb 在 staging/libs 里（venv 里没有），跟 forward_template_mining.py 同一处理
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402

COND = STAGE / "reports" / "conditions_normalized.json"
BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"

print("=" * 92)
print("[1] SmartReact 门控的类名（conditions_normalized.json 的 key）")
print("=" * 92)
d = json.loads(COND.read_text(encoding="utf-8"))
keys = sorted(d.keys())
print(f"  共 {len(keys)} 个：")
for i in range(0, len(keys), 4):
    print("   " + "  ".join(f"{k:<36}" for k in keys[i:i + 4]))

print()
print("=" * 92)
print("[2] ORD parquet 的 reaction 字段取值（前 25，按频次）")
print("=" * 92)
con = duckdb.connect()
rows = con.execute(f"""
    SELECT reaction AS r, count(*) AS n
    FROM read_parquet('{BIG.as_posix()}')
    GROUP BY 1 ORDER BY n DESC LIMIT 25
""").fetchall()
for r, n in rows:
    print(f"   {n:>8,}  {str(r)[:70]!r}")

n_total, n_distinct = con.execute(f"""
    SELECT count(*), count(DISTINCT reaction) FROM read_parquet('{BIG.as_posix()}')
""").fetchone()
print(f"\n  总记录 {n_total:,}，reaction 去重 {n_distinct:,}")

print()
print("=" * 92)
print("[3] 能不能直接对上？")
print("=" * 92)
ord_names = {str(r) for r, _ in rows}
inter = ord_names & set(keys)
print(f"  ORD 前 25 名 与 37 类名的交集：{sorted(inter) if inter else '空 —— 对不上'}")
print(f"  37 类名里含连字符/大写的（可能是 ORD 风格）：")
print("   " + ", ".join(k for k in keys if not k.islower() or "-" in k))
