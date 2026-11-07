# -*- coding: utf-8 -*-
r"""探 coconut.db 的实际规模与结构（只读表结构+计数，不读数据本体）。"""
import sqlite3
from pathlib import Path

DB = Path(r"D:\TCMAI\coconut.db")
print(f"文件: {DB}  ({DB.stat().st_size/1024**2:.1f} MB)")
print("=" * 88)

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()

cur.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view')")
objs = cur.fetchall()
print(f"表/视图 {len(objs)} 个：")
for name, typ in objs:
    try:
        n = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"   {name:<28} {typ:<6} {n:>9,} 行")
    except Exception as ex:
        print(f"   {name:<28} {typ:<6} (计数失败: {str(ex)[:40]})")

# compounds 表列
print()
print("=" * 88)
print("compounds 表结构")
print("=" * 88)
cur.execute("PRAGMA table_info(compounds)")
cols = cur.fetchall()
for c in cols:
    print(f"   {c[1]:<24} {c[2]}")

# 关键：有没有 inchi 类字段（用于回查预测产物）
names = [c[1].lower() for c in cols]
has_inchi = [n for n in names if "inchi" in n]
print(f"   ★ 含 inchi 的列: {has_inchi or '无'}")

# 甘草（Glycyrrhiza）在 COCONUT 里有多少化合物？
print()
print("=" * 88)
print("对照：tcm.db 的「甘草」 vs COCONUT 的 Glycyrrhiza")
print("=" * 88)
try:
    cur.execute("SELECT name FROM sqlite_master WHERE name LIKE '%species%'")
    sp_tables = [r[0] for r in cur.fetchall()]
    print(f"   含 species 的表: {sp_tables}")
    for st in sp_tables:
        cur.execute(f"PRAGMA table_info({st})")
        print(f"   {st} 列: {[c[1] for c in cur.fetchall()]}")
except Exception as ex:
    print(f"   查询失败: {ex}")

for kw in ("Glycyrrhiza", "glycyrrhiza"):
    try:
        cur.execute("""SELECT COUNT(DISTINCT sc.cnp_id) FROM species_compound sc
                       WHERE LOWER(sc.species) LIKE ?""", (f"%{kw.lower()}%",))
        n = cur.fetchone()[0]
        print(f"   COCONUT 里 species 含 '{kw}' 的化合物: {n:,}")
    except Exception as ex:
        print(f"   '{kw}' 查询失败: {str(ex)[:60]}")
        break

con.close()
