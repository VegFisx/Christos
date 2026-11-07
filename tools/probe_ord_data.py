# -*- coding: utf-8 -*-
r"""探 ORD parquet 结构：schema + 各文件行数（只读 footer，不加载数据本体）。

1.17 GB / 53 个 parquet，本机可用内存只有 ~4.7 GB -> 必须低内存方式。
用 duckdb 读 parquet metadata（只读页脚，极便宜）。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

import duckdb  # noqa: E402

ORD = STAGE / "ord-data"
pq = sorted((ORD / "data").rglob("*.parquet"))
print("=" * 78)
print(f"parquet 文件 {len(pq)} 个")
print("=" * 78)

con = duckdb.connect()
con.execute("SET memory_limit='1500MB'")
con.execute("SET threads=2")

# ---- ① 各文件行数（读 metadata，不加载数据）----
print("\n① 各文件行数（前 15 个 + 合计）")
rows_total = 0
sizes = []
for p in pq:
    try:
        n = con.execute(
            f"SELECT num_rows FROM parquet_file_metadata('{p.as_posix()}')"
        ).fetchone()[0]
    except Exception as ex:
        # 退化：用 count(*)
        try:
            n = con.execute(f"SELECT count(*) FROM read_parquet('{p.as_posix()}')").fetchone()[0]
        except Exception as ex2:
            print(f"   ✗ {p.name}: {ex2}")
            continue
    rows_total += n
    sizes.append((n, p.name))
sizes.sort(reverse=True)
for n, name in sizes[:15]:
    print(f"   {n:>9,}  {name}")
print(f"   ... 共 {len(sizes)} 个文件")
print(f"   ★ 总行数 {rows_total:,}")

# ---- ② schema（挑最大的那个文件）----
print("\n② schema（取最大的 parquet）")
big = max(pq, key=lambda x: x.stat().st_size)
print(f"   文件: {big.name}  ({big.stat().st_size/1024**2:.1f} MB)")
desc = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{big.as_posix()}')").fetchall()
for col, typ, *rest in desc:
    print(f"   {col:<28} {typ}")

# ---- ③ 抽样看形状（只 2 行，截断字段）----
print("\n③ 抽样 2 行（字段截断到 160 字符）")
try:
    cur = con.execute(f"SELECT * FROM read_parquet('{big.as_posix()}') LIMIT 2")
    names = [d[0] for d in cur.description]
    for r in cur.fetchall():
        print("   " + "-" * 60)
        for k, v in zip(names, r):
            s = str(v)
            if len(s) > 160:
                s = s[:160] + f"…(共 {len(s)} 字符)"
            print(f"   {k:<26} = {s}")
except Exception as ex:
    print(f"   ✗ {type(ex).__name__}: {str(ex)[:200]}")

con.close()
