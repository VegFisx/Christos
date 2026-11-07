# -*- coding: utf-8 -*-
r"""探针：单底物记录里的【非贡献组分】是不是就是试剂（还原剂/酸/碱）？

## 推理
`contributing_components` 只保留"映射原子 >50% 进产物"的组分。
**NaBH₄ / H₂ 的原子不进产物** -> 它们不算贡献组分 -> 整条记录看起来是"单底物"。
所以：**那些非贡献组分，很可能就是被 ORD 标成 REACTANT 的试剂**。
若能确认，就能把它们填进 `Conditions.reagents` —— 第二十四轮那个净亏的氧化还原门控就有救了。

口径：`reactants` 列（带映射的 CXSMILES 左侧），按 "." 拆组件，逐组件算 map_nums 与产物的交集比例。
"""
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
# ★ duckdb 在 staging/libs 里 —— 必须在 import 之前加 sys.path（本次会话第 4 次踩）
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
SEED = 20261013

con = duckdb.connect()
df = con.execute(f"""
    SELECT reactants, product FROM read_parquet('{SHARDS}')
    USING SAMPLE {N} ROWS (reservoir, {SEED})
""").fetchdf()

HYDRIDE_HINTS = ("[BH4-]", "[BH3-]", "[AlH4-]", "[H][H]", "[SiH]", "[BH]")
OXIDANT_HINTS = ("O=O", "OO", "[Mn", "[Cr", "[I](", "Cl(=O)")

n_mono = n_with_noncontrib = 0
small_agents = Counter()
n_hydride = n_oxidant = 0
examples = []
for lhs, rhs in zip(df["reactants"], df["product"]):
    pm = mc.parse_plain(str(rhs))
    if pm is None:
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        continue
    parts = [x for x in str(lhs or "").split(".") if x]
    contrib, noncontrib = [], []
    for p in parts:
        m = mc.parse_plain(p)
        if m is None:
            continue
        nums = mc.map_nums(m)
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            contrib.append(p)
        else:
            noncontrib.append(p)
    if len(contrib) != 1:
        continue
    n_mono += 1
    if noncontrib:
        n_with_noncontrib += 1
        for p in noncontrib:
            cs = mc.canon_plain(p)
            if cs:
                small_agents[cs] += 1
                if any(h in p for h in HYDRIDE_HINTS):
                    n_hydride += 1
                    if len(examples) < 8:
                        examples.append(("还原剂", p, cs))
                elif any(h in p for h in OXIDANT_HINTS):
                    n_oxidant += 1
                    if len(examples) < 8:
                        examples.append(("氧化剂", p, cs))

print("=" * 100)
print(f"单底物记录里的非贡献组分（抽样 {N:,}）")
print("=" * 100)
print(f"  单底物记录（贡献组分=1）：{n_mono:,}")
print(f"  其中【有非贡献组分】的：{n_with_noncontrib:,} = "
      f"{n_with_noncontrib/max(1,n_mono):.1%}")
print(f"  非贡献组分里匹配【氢化物/H2】模式的：{n_hydride:,} 个")
print(f"  非贡献组分里匹配【氧化剂】模式的：{n_oxidant:,} 个")
print(f"\n  非贡献组分 Top 20：")
for smi, n in small_agents.most_common(20):
    print(f"    {n:>6}  {smi[:80]}")
print(f"\n  氢化物/氧化剂样例：")
for tag, raw, cs in examples:
    print(f"    [{tag}] raw={raw[:60]}  canon={cs[:50]}")
