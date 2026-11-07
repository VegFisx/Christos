# -*- coding: utf-8 -*-
r"""用【真实共试剂】重测「必需试剂判零」——这条判据以前从没在真实试剂上跑过。

## 背景
第二十五轮发现：`Conditions.reagents` 一直是空的（ORD 的 `reagent_*` 列 = 0%），
所以 `cond_activation()` 里那条「条件里没写试剂就不检查」的后门**永远在生效** ——
**"必需试剂判零（6/37 类）"在真实数据上根本触发不了。**

现在有了 `co_reagents`（从非贡献组分抽出来的真实试剂），可以做两件事：
  ① 量它**触发率**（有多少真实反应会因为缺必需试剂被judged zero）
  ② 量**误杀率**（真实发生过的反应被判零 = 误杀）

口径：ORD 分片里取**恰好 2 个贡献组分**的记录（引擎能尝试的那批），
      条件用记录自己的温度/溶剂，试剂分别给 () 与 co_reagents。
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
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core", STAGE / "conditions",
           STAGE / "rules"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402
import model as M  # noqa: E402
from engine import Compound  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
CO = (STAGE / "reports" / "ord_co_reagents" / "shard_*.parquet").as_posix()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
SEED = 20261013
MAX_CASES = 1200

if not list((STAGE / "reports" / "ord_co_reagents").glob("*.parquet")):
    print("先跑 tools/extract_co_reagents.py 生成 co_reagents")
    sys.exit(1)

con = duckdb.connect()
df = con.execute(f"""
    WITH s AS (
        SELECT reaction_id, reactants, product, temperature_C, solvent_names
        FROM read_parquet('{SHARDS}')
        USING SAMPLE {N} ROWS (reservoir, {SEED})
    ),
    c AS (SELECT reaction_id, co_reagents FROM read_parquet('{CO}'))
    SELECT s.*, c.co_reagents FROM s LEFT JOIN c USING (reaction_id)
""").fetchdf()

cases = []
skip = Counter()
for rid, lhs, rhs, temp, solv, co in zip(df["reaction_id"], df["reactants"], df["product"],
                                        df["temperature_C"], df["solvent_names"],
                                        df["co_reagents"]):
    pm = mc.parse_plain(str(rhs))
    if pm is None:
        skip["产物非法"] += 1
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        skip["产物无映射"] += 1
        continue
    contrib = []
    for p in [x for x in str(lhs or "").split(".") if x]:
        m = mc.parse_plain(p)
        if m is None:
            continue
        nums = mc.map_nums(m)
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            cs = mc.canon_plain(p)
            if cs:
                contrib.append(cs)
    if len(contrib) != 2:
        skip[f"贡献组分={len(contrib)}"] += 1
        continue
    wants = {mc.canon_plain(x) for x in str(rhs).split(".") if x.strip()}
    wants.discard(None)
    reag = tuple(x for x in str(co or "").split(";") if x)
    cases.append((sorted(contrib), wants, temp, solv, reag))
    if len(cases) >= MAX_CASES:
        break

n_reag = sum(1 for c in cases if c[4])
print("=" * 100)
print(f"必需试剂判零 · 真实试剂复测：用例 {len(cases):,}（抽样 {N:,}，seed {SEED}）")
print(f"  其中【带真实共试剂】的 {n_reag:,} = {n_reag/max(1,len(cases)):.1%}")
print(f"  跳过：{dict(skip)}")
print("=" * 100)


def cond_of(temp, solv, reagents):
    s = str(solv or "").lower()
    sol = "water" if ("water" in s or "h2o" in s) else (s.split(";")[0].split(",")[0].strip() or "water")
    t = float(temp) if temp is not None and temp == temp else 100.0
    return M.Conditions(solvent=sol, temperature=t, time_min=60.0, atmosphere="air",
                        reagents=tuple(reagents))


for label, use_reag in (("A 条件不带试剂（现状）", False), ("B 条件带真实共试剂", True)):
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False, verbose=False)
    hit = active = 0
    gz = 0
    gz_types = Counter()
    for subs, wants, temp, solv, reag in cases:
        cond = cond_of(temp, solv, reag if use_reag else ())
        comps = [Compound(smiles=s, name="x", herb="ord") for s in subs]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            continue
        got = {mc.canon_plain(p.smiles) for p in prods}
        got.discard(None)
        if got:
            active += 1
        if wants & got:
            hit += 1
        gz += eng.stats.get("gated_zero_total", 0)
        for k, v in (eng.stats.get("gated_zero_by_type") or {}).items():
            gz_types[k] += v
    n = max(1, len(cases))
    print(f"\n[{label}]")
    print(f"  命中记录产物 {hit:,}/{n:,} = **{hit/n:.1%}**   活性 {active/n:.1%}   "
          f"门控判零总数 {gz:,}   耗时 {time.time()-t0:.1f}s")
    if gz_types:
        print(f"  判零最多的类型：{dict(gz_types.most_common(8))}")
