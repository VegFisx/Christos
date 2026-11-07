# -*- coding: utf-8 -*-
r"""抽取 ORD 的【共试剂】列（co_reagents）—— 补上条件层一直缺的输入。

## 依据（第二十五轮实测）
`reagent_names`/`reagent_smiles` 两列 **0%**，但 **"非贡献组分"就是试剂**：
`contributing_components()` 只保留"映射原子 >50% 进产物"的组分，而还原剂/氧化剂/酸碱的原子大多不进产物
-> 它们被排到"非贡献"那一侧。实测：单底物记录 81.6% 带非贡献组分，Top 是
`[Na+]`/`[OH-]`/`[H-]`/`[BH4-]`(766)/`[H][H]`(521)/`[Al+3]`/TFA/AcOH/Et3N。

## 产出
`reports/ord_co_reagents/shard_XXXX.parquet`（列：reaction_id, co_reagents(分号连接), n_co）
逐分片写、存在即跳过（可续跑）；末尾打印覆盖率与 Top 试剂。

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\extract_co_reagents.py
"""
from __future__ import annotations

import json
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
# ★ duckdb 在 staging/libs 里 —— 必须在 import 之前加 sys.path
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SRC = STAGE / "reports" / "ord_condition_dataset"
OUT = STAGE / "reports" / "ord_co_reagents"
HYDRIDE = ("[BH4-]", "[BH3-]", "[BH]", "[AlH", "[Al+3]", "[H-]", "[H][H]", "[SiH]")
OXIDANT = ("O=O", "OO", "[Mn", "[Cr", "[I](", "Cl(=O)", "OS(=O)(=O)O", "[O-][O-]")

OUT.mkdir(parents=True, exist_ok=True)
shards = sorted(SRC.glob("shard_*.parquet"))
print("=" * 100)
print(f"抽取共试剂（co_reagents）：{len(shards)} 个分片 -> {OUT}")
print("=" * 100, flush=True)

con = duckdb.connect()
fail = Counter()
top = Counter()
n_rows = n_with = n_hyd = n_oxi = 0
t0 = time.time()
for i, sp in enumerate(shards):
    dst = OUT / sp.name
    if dst.exists():
        continue
    df = con.execute(f"""
        SELECT reaction_id, reactants, product FROM read_parquet('{sp.as_posix()}')
    """).fetchdf()
    ids, cos, ns = [], [], []
    for rid, lhs, rhs in zip(df["reaction_id"], df["reactants"], df["product"]):
        n_rows += 1
        pm = mc.parse_plain(str(rhs)) if rhs else None
        if pm is None:
            fail["产物非法"] += 1
            ids.append(rid); cos.append(""); ns.append(0)
            continue
        pmaps = mc.map_nums(pm)
        if not pmaps:
            fail["产物无映射"] += 1
            ids.append(rid); cos.append(""); ns.append(0)
            continue
        co = []
        for p in [x for x in str(lhs or "").split(".") if x]:
            m = mc.parse_plain(p)
            if m is None:
                fail["组分非法"] += 1
                continue
            nums = mc.map_nums(m)
            if nums and len(nums & pmaps) / len(nums) > 0.5:
                continue                    # 贡献组分（底物）-> 不要
            cs = mc.canon_plain(p)
            if cs:
                co.append(cs)
        co = sorted(set(co))
        if co:
            n_with += 1
            for c in co:
                top[c] += 1
            if any(h in " ".join(co) for h in HYDRIDE):
                n_hyd += 1
            if any(h in " ".join(co) for h in OXIDANT):
                n_oxi += 1
        ids.append(rid); cos.append(";".join(co)); ns.append(len(co))
    pd.DataFrame({"reaction_id": ids, "co_reagents": cos, "n_co": ns}).to_parquet(dst, index=False)
    if (i + 1) % 20 == 0 or i == len(shards) - 1:
        print(f"  [{i+1}/{len(shards)}] 行 {n_rows:,}  带试剂 {n_with:,} "
              f"({n_with/max(1,n_rows):.1%})  氢化物 {n_hyd:,}  氧化剂 {n_oxi:,}  "
              f"{time.time()-t0:.0f}s", flush=True)

print(f"\n  合计行 {n_rows:,}；带共试剂 {n_with:,} = {n_with/max(1,n_rows):.1%}")
print(f"  含氢化物/H2 类 {n_hyd:,} = {n_hyd/max(1,n_rows):.1%}；含氧化剂类 {n_oxi:,} = {n_oxi/max(1,n_rows):.1%}")
print(f"  失败分类：{dict(fail)}")
print(f"\n  共试剂 Top 20：")
for c, k in top.most_common(20):
    print(f"    {k:>7}  {c[:70]}")
(Path(STAGE / "reports" / "ord_co_reagents_summary.json")).write_text(json.dumps({
    "scratch": "从 ORD 的非贡献组分抽取共试剂（第二十五轮发现的落地）",
    "n_rows": n_rows, "n_with_reagents": n_with,
    "rate_with_reagents": n_with / max(1, n_rows),
    "n_hydride_like": n_hyd, "n_oxidant_like": n_oxi,
    "fail": dict(fail), "top20": top.most_common(20), "seconds": round(time.time() - t0, 1),
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {OUT}  与 ord_co_reagents_summary.json", flush=True)
