# -*- coding: utf-8 -*-
r"""探 smartreact API + 测速：用模板自带的 example 跑一小批，估算全量 9770 条要多久。"""
import sys
import time
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from smartreact import ReactionEnumerator  # noqa: E402

# ---------- 读 templates.txt ----------
P = STAGE / "libs" / "smartreact" / "data" / "templates.txt"
rows = []
for line in P.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
    f = line.split("\t")
    if len(f) == 5:
        rows.append(f)
print(f"数据行 {len(rows)}")

# ---------- example 的底物个数分布 ----------
def split_ex(ex):
    lhs, rhs = ex.split(">>", 1)
    return [s for s in lhs.split(".") if s], rhs

n_re = Counter(len(split_ex(r[2])[0]) for r in rows)
print(f"底物个数分布: {dict(n_re)}")

# ---------- API 探测 ----------
t0 = time.time()
enum = ReactionEnumerator()
print(f"\n构造 ReactionEnumerator 耗时 {time.time()-t0:.2f}s")
print("公开属性/方法:")
for a in sorted(dir(enum)):
    if a.startswith("_"):
        continue
    print(f"    {a}")

# ---------- 单条试跑 ----------
r0 = rows[0]
smis, prod = split_ex(r0[2])
print("\n" + "=" * 78)
print(f"试跑第 1 条: {r0[0]} / id={r0[1]}")
print(f"  底物: {smis}")
print(f"  期望产物: {prod}")
print("=" * 78)
try:
    res = enum.enumerate_pair(smis[0], smis[1])
    print(f"  返回类型: {type(res).__name__}, 长度 {len(res)}")
    if res:
        x = res[0]
        print(f"  元素类型: {type(x).__name__}")
        print(f"  元素属性: {[a for a in dir(x) if not a.startswith('_')]}")
        for i, x in enumerate(res[:3]):
            nm = getattr(x, "reaction_name", "?")
            pr = getattr(x, "products", None)
            print(f"    [{i}] name={nm} products={list(pr)[:2] if pr else pr}")
except Exception as ex:
    print(f"  ✗ {type(ex).__name__}: {str(ex)[:300]}")

# ---------- 测速：抽 40 条 ----------
print("\n" + "=" * 78)
print("测速：抽 40 条")
print("=" * 78)
t0 = time.time()
ok = err = 0
for r in rows[:40]:
    smis, prod = split_ex(r[2])
    try:
        enum.enumerate_pair(smis[0], smis[1])
        ok += 1
    except Exception:
        err += 1
dt = time.time() - t0
print(f"  40 条耗时 {dt:.2f}s  ->  单条 {dt/40*1000:.1f} ms")
print(f"  成功 {ok} / 异常 {err}")
print(f"  ★ 全量 9770 条预计 {9770*dt/40/60:.1f} 分钟")
