# -*- coding: utf-8 -*-
r"""全量普查：ORD 里【贡献组分】个数分布 —— 决定"引擎到底能尝试多少记录"。

## 为什么要重算
第十八轮我用**原始组分个数**得出"只有 30.27% 是 2 组分、65% 进不来"。
但引擎真正需要的是**贡献组分**（原子进产物的那些）个数：
ORD 提交者常把碱/试剂也标成 REACTANT，所以原始组分多 ≠ 贡献组分多。
（`forward_template_mining.py` 自己的跳过统计就有暗示：40k 抽样里 `贡献组分=2` 有 26,884。
粗略算 26,884/40,000 = 67%，**远高于 30.27%**。）

本脚本在全量 925,943 行上把这件事定死，并与"原始组分"分布并列对照。
"""
from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
CO = (STAGE / "reports" / "ord_co_reagents" / "shard_*.parquet").as_posix()

con = duckdb.connect()
print("=" * 100)
print("全量普查：贡献组分 vs 原始组分")
print("=" * 100, flush=True)

t0 = time.time()
df = con.execute(f"""
    SELECT reactants, product FROM read_parquet('{SHARDS}')
""").fetchdf()
print(f"  读取 {len(df):,} 行（{time.time()-t0:.0f}s）", flush=True)

raw_dist = Counter()
con_dist = Counter()
no_map = 0
examples = {}
t0 = time.time()
for lhs, rhs in zip(df["reactants"], df["product"]):
    parts = [x for x in str(lhs or "").split(".") if x]
    raw_dist[len(parts)] += 1
    pm = mc.parse_plain(str(rhs)) if rhs else None
    if pm is None:
        no_map += 1
        con_dist["解析失败"] += 1
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        no_map += 1
        con_dist["产物无映射"] += 1
        continue
    n_c = 0
    for p in parts:
        m = mc.parse_plain(p)
        if m is None:
            continue
        nums = mc.map_nums(m)
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            n_c += 1
    con_dist[n_c] += 1
    if n_c >= 3 and len(examples.get(n_c, [])) < 2:
        examples.setdefault(n_c, []).append(str(lhs)[:120])

n = len(df)
print(f"  统计完成（{time.time()-t0:.0f}s）\n", flush=True)

print("  [1] 原始组分个数分布（第十八轮用的口径）")
for k in sorted(x for x in raw_dist if isinstance(x, int)):
    print(f"      {k} 个：{raw_dist[k]:>9,}  {raw_dist[k]/n:6.1%}")

print("\n  [2] ★ 贡献组分个数分布（引擎真正在意的口径）")
for k in sorted(x for x in con_dist if isinstance(x, int)):
    tag = ""
    if k == 1:
        tag = "  <- 单底物模板可处理"
    elif k == 2:
        tag = "  <- 双底物模板可处理（主路径）"
    elif k >= 3:
        tag = "  <- 需要 3+ 反应物模板（当前引擎不支持）"
    print(f"      {k} 个：{con_dist[k]:>9,}  {con_dist[k]/n:6.1%}{tag}")
for k in ("产物无映射", "解析失败"):
    if con_dist.get(k):
        print(f"      {k}：{con_dist[k]:>9,}  {con_dist[k]/n:6.1%}")

ok = sum(v for k, v in con_dist.items() if isinstance(k, int))
print(f"\n  ★ 可尝试（贡献组分 1 或 2）："
      f"{(con_dist.get(1,0)+con_dist.get(2,0)):,} = {(con_dist.get(1,0)+con_dist.get(2,0))/max(1,ok):.1%}（占有映射的行）")
print(f"  ★ 需要 3+（当前不支持）：{sum(v for k,v in con_dist.items() if isinstance(k,int) and k>=3):,}"
      f" = {sum(v for k,v in con_dist.items() if isinstance(k,int) and k>=3)/max(1,ok):.1%}")

print("\n  3+ 贡献组分样例（看它们是不是真的多组分反应）：")
for k in sorted(examples):
    for e in examples[k]:
        print(f"      [{k}组分] {e}")
