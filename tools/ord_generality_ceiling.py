# -*- coding: utf-8 -*-
r"""Phase 1 口径定义性测量：**通用性的天花板卡在哪？**

## 为什么先测这个
用户要的顺序是「**先做通用产物预测，再用现实条件约束**」。所以 Phase 1 的目标是**通用性**，
而通用性现在有三处**自己给自己设的上限**（都来自本工作区已实测的事实）：
  · SmartReact 模板加载时**只保留恰好 2 个反应物**的模板（rdkit_template_lib.compile_templates）
  · 模板只从 ORD 的 **4 万抽样**里挖过（全量 177 万）
  · 挖掘时**跳过重原子 > 70** 的分子（1,593 条）

## 这个脚本只回答 4 个问题（不跑引擎、不改任何东西）
  1. ORD 全量 177 万条里，反应物个数分布是什么？（1 / 2 / 3 / 4+ 各多少）
  2. 当前引擎**能碰**的记录有多少（恰好 2 个可解析反应物）？若放开到 n 组分，能碰多少？
  3. 分子大小分布：反应物与产物在 MW / 重原子上的分位（看"大分子化学"缺位有多严重）
  4. ORD 的产物有多少是 **COCONUT 已知天然产物**（库级标尺的可行性）

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\ord_generality_ceiling.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
# ★ duckdb 在 staging/libs 里（venv 没有），必须在 import 之前加进 sys.path
for _p in (STAGE / "libs", STAGE / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
import numpy as np  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")
SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
COCO = STAGE / "reports" / "coconut_inchikey_index.jsonl"
SEED = 20261013
N_DESC = 20000

con = duckdb.connect()
print("=" * 96)
print("Phase 1：通用性天花板分解（ORD 全量）")
print("=" * 96)

n_all = con.execute(f"SELECT count(*) FROM read_parquet('{SHARDS}')").fetchone()[0]
print(f"  ORD 条件表总行数：{n_all:,}")

# ---------------------------------------------------------------- 1. 反应物个数分布
df = con.execute(f"""
    SELECT reaction_id, reactants_n, reactant_smiles_components, product_smiles,
           temperature_C, yield_percent
    FROM read_parquet('{SHARDS}')
""").fetchdf()
df["_comps"] = df["reactant_smiles_components"].fillna("").astype(str)
df["_n_comp"] = df["_comps"].map(lambda s: len([x for x in s.split(";") if x.strip()]))

print("\n[1] 反应物组分个数分布（按 reactant_smiles_components 分号拆）")
vc = df["_n_comp"].value_counts().sort_index()
for k, v in vc.items():
    print(f"    {int(k)} 个组分：{v:>9,}  ({v/n_all:6.2%})")
n2 = int((df["_n_comp"] == 2).sum())
print(f"    ★ 恰好 2 个：{n2:,} ({n2/n_all:.2%})   ← 当前引擎只能碰这一档")

# ---------------------------------------------------------------- 2. 能碰到多少
print("\n[2] 当前引擎 vs 放开口径的『可尝试』上限")
print(f"    当前（恰好 2 组分）：        {n2:>9,}  = {n2/n_all:6.2%}")
ge2 = int((df["_n_comp"] >= 2).sum())
print(f"    放开到 >=2 组分（n 组分模板）：{ge2:>9,}  = {ge2/n_all:6.2%}   "
      f"（+{ge2-n2:,}，相对现在 {ge2/max(1,n2):.2f}x）")
ge1 = int((df["_n_comp"] >= 1).sum())
print(f"    放开到 >=1 组分：            {ge1:>9,}  = {ge1/n_all:6.2%}")
print("    ⚠ 注意：**这是可达性的上界**。ORD 提交者常把碱/添加剂也标成 REACTANT 角色，")
print("      所以 3+ 组分里有一部分不是真·多组分反应。下面 [2b] 专门量这件事。")

# ---------------------------------------------------------------- 2b. 3+ 组分是真反应物还是被误标的试剂
print("\n[2b] 『3 个组分』里，第三个到底是不是真反应物？（抽 5000 条 3 组分记录）")
sub3 = df[df["_n_comp"] == 3].sample(n=min(5000, int((df["_n_comp"] == 3).sum())),
                                     random_state=SEED)
sizes = []          # 每条记录：3 个组分的重原子数（解析成功才算）
parse_fail = 0
for comps in sub3["_comps"]:
    hs = []
    for c in [x for x in comps.split(";") if x.strip()]:
        mm = Chem.MolFromSmiles(c)
        if mm is None:
            parse_fail += 1
            continue
        hs.append(mm.GetNumHeavyAtoms())
    if len(hs) == 3:
        sizes.append(sorted(hs))
if sizes:
    arr = np.asarray(sizes)
    smallest = arr[:, 0]
    largest = arr[:, 2]
    ratio = smallest / np.maximum(largest, 1)
    print(f"    可用记录 {len(sizes):,}（SMILES 解析失败 {parse_fail} 个）")
    print(f"    最小组分的重原子数：中位 {np.median(smallest):.0f}  "
          f"p10 {np.percentile(smallest,10):.0f}  p90 {np.percentile(smallest,90):.0f}")
    for thr in (6, 10, 15):
        print(f"      最小组分 重原子<= {thr:<3}: {(smallest<=thr).mean():6.2%}"
              f"    <- 很可能是碱/试剂被标成 REACTANT")
    print(f"      三个组分都 >=15 重原子（像真·三组分）：{(smallest>=15).mean():6.2%}")
    print(f"      最小/最大 尺寸比 中位 {np.median(ratio):.2f}")
    print(f"      【推断】3 组分里真·多组分的比例量级：约 {max(0.0,(smallest>=15).mean()):.1%}"
          f" ~ {(smallest>10).mean():.1%}")
else:
    print("    无可用记录")

# ---------------------------------------------------------------- 3. 分子大小
print(f"\n[3] 分子大小分布（固定 seed 抽 {N_DESC:,} 行算描述符）")
smp = df.sample(n=min(N_DESC, len(df)), random_state=SEED)


def desc_of(smi: str):
    m = Chem.MolFromSmiles(str(smi))
    if m is None:
        return None
    return (Descriptors.MolWt(m), m.GetNumHeavyAtoms(), m.GetRingInfo().NumRings(),
            rdMolDescriptors.CalcNumBridgeheadAtoms(m) if m.GetNumHeavyAtoms() > 2 else 0)


fail_react = fail_prod = 0
mw_r, ha_r, mw_p, ha_p = [], [], [], []
for comps, prod in zip(smp["_comps"], smp["product_smiles"]):
    for c in [x for x in comps.split(";") if x.strip()]:
        d = desc_of(c)
        if d is None:
            fail_react += 1
            continue
        mw_r.append(d[0]); ha_r.append(d[1])
    d = desc_of(prod)
    if d is None:
        fail_prod += 1
    else:
        mw_p.append(d[0]); ha_p.append(d[1])

for lab, mw, ha in (("反应物", mw_r, ha_r), ("产物", mw_p, ha_p)):
    if not mw:
        continue
    a, b = np.asarray(mw), np.asarray(ha)
    print(f"    {lab}：MW 中位 {np.median(a):7.1f}  p90 {np.percentile(a,90):7.1f}  "
          f"max {a.max():8.1f}  |  重原子 中位 {np.median(b):5.1f}  p90 {np.percentile(b,90):5.1f}")
    for thr in (300, 600, 1000):
        print(f"        MW>{thr:<5}: {(a>thr).mean():6.2%}", end="")
    print()
    for thr in (22, 40, 70):
        print(f"        重原子>{thr:<3}: {(b>thr).mean():6.2%}", end="")
    print()
print(f"    解析失败：反应物 {fail_react} 个 SMILES，产物 {fail_prod} 条记录")

# ---------------------------------------------------------------- 4. 产物是否命中 COCONUT
print("\n[4] ORD 产物里有多少是 COCONUT 已知天然产物（库级标尺可行性）")
print("    COCONUT 索引首行（原始，先看格式再解析）：")
first = COCO.open(encoding="utf-8").readline().strip()
print(f"      {first[:160]}")
# ★ 实测格式：制表符分隔的「InChIKey \t np_likeness」，不是 JSON（第一版按 JSON 解析 -> 0 命中，已修）
keys_full, keys_skel, n_line = set(), set(), 0
for line in COCO.open(encoding="utf-8"):
    parts = line.strip().split()
    if not parts:
        continue
    n_line += 1
    ik = parts[0]
    keys_full.add(ik)
    keys_skel.add(ik.split("-")[0])
print(f"    索引行数 {n_line:,}  完整键 {len(keys_full):,}  骨架键(前段) {len(keys_skel):,}")

hit_ex = hit_sk = tot = 0
hit_sk_big = tot_big = 0
for prod in smp["product_smiles"]:
    m = Chem.MolFromSmiles(str(prod))
    if m is None:
        continue
    try:
        ik = Chem.MolToInchiKey(m)
    except Exception:
        continue
    tot += 1
    big = m.GetNumHeavyAtoms() >= 25
    if big:
        tot_big += 1
    if ik in keys_full:
        hit_ex += 1
    if ik.split("-")[0] in keys_skel:
        hit_sk += 1
        if big:
            hit_sk_big += 1
print(f"    抽样产物 {tot:,} 条：")
print(f"      完整 InChIKey 命中 COCONUT **{hit_ex:,} = {hit_ex/tot:.2%}**（同一化合物）")
print(f"      骨架(InChIKey 前段)命中    **{hit_sk:,} = {hit_sk/tot:.2%}**（同一骨架家族）")
print(f"      其中重原子>=25 的 {tot_big:,} 条里骨架命中 {hit_sk_big:,} = "
      f"{(hit_sk_big/tot_big if tot_big else 0):.2%}")
print("\n  ★ 读法：命中率高 -> COCONUT 能当产物宇宙、ORD 与天然产物空间重叠大；")
print("     命中率低 -> ORD 主要是合成化学，天然产物专属标尺要另找数据源。")
