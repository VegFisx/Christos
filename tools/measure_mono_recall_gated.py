# -*- coding: utf-8 -*-
r"""门控的收益测量：在【真实单底物记录 + 记录自己的条件】上，三配置对比。

配置：
  A 单底物模板关                       （第二十二轮前的旧行为）
  B 单底物模板开 + 门控关（cond=None）  （第二十三轮行为：全放行）
  C 单底物模板开 + 氧化还原气氛门控开 + 用记录的真实条件（温度/溶剂/空气）
指标：命中记录产物 / 有产物（活性）。数据源：reports/ord_condition_dataset 分片（含条件列）。
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
N = int(sys.argv[1]) if len(sys.argv) > 1 else 60000
SEED = 20261013
MAX_MONO = 1500

con = duckdb.connect()
df = con.execute(f"""
    SELECT reactants, product, temperature_C, solvent_names
    FROM read_parquet('{SHARDS}')
    USING SAMPLE {N} ROWS (reservoir, {SEED})
""").fetchdf()

cases = []
skip = Counter()
for lhs, rhs, temp, solv in zip(df["reactants"], df["product"], df["temperature_C"],
                               df["solvent_names"]):
    if not lhs or not rhs:
        skip["缺 SMILES"] += 1
        continue
    pm = mc.parse_plain(str(rhs))
    if pm is None:
        skip["产物非法"] += 1
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        skip["产物无映射"] += 1
        continue
    raws, plains = mc.contributing_components(str(lhs), pmaps)
    if len(plains) != 1:
        skip[f"贡献组分={len(plains)}"] += 1
        continue
    wants = {mc.canon_plain(x) for x in str(rhs).split(".") if x.strip()}
    wants.discard(None)
    if not wants:
        skip["产物归一失败"] += 1
        continue
    cases.append((plains[0], wants, temp, solv))
    if len(cases) >= MAX_MONO:
        break

print("=" * 100)
print(f"门控收益测量：真实单底物记录 {len(cases):,} 条（抽样 {N:,}，seed {SEED}）")
print(f"  跳过：{dict(skip)}")
print("=" * 100)


def cond_of(temp, solv):
    s = str(solv or "").lower()
    if "water" in s or "h2o" in s:
        sol = "water"
    elif s:
        sol = s.split(";")[0].split(",")[0].strip() or "water"
    else:
        sol = "water"
    t = float(temp) if temp is not None and temp == temp else 100.0
    return M.Conditions(solvent=sol, temperature=t, time_min=60.0, atmosphere="air")


CONFIGS = [
    ("A 模板关", dict(use_mono_templates=False), "none"),
    ("B 模板开 + 门控关", dict(use_mono_templates=True, mono_redox_gate=False), "none"),
    ("C 模板开 + 门控开 + 真实条件", dict(use_mono_templates=True, mono_redox_gate=True), "real"),
]
for label, kw, condmode in CONFIGS:
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False, **kw)
    hit = active = 0
    for smi, wants, temp, solv in cases:
        cond = None if condmode == "none" else cond_of(temp, solv)
        try:
            prods = eng.step([Compound(smiles=smi, name="x", herb="ord")], cond, round_no=1)
        except Exception:
            continue
        got = {mc.canon_plain(p.smiles) for p in prods}
        got.discard(None)
        if got:
            active += 1
        if wants & got:
            hit += 1
    n = max(1, len(cases))
    extra = ""
    if kw.get("use_mono_templates"):
        g = {k: v for k, v in eng.gate_stats.items() if "单底物" in k}
        extra = f"   门控统计 {g}" if g else ""
    print(f"\n[{label}]")
    print(f"  命中 {hit:,}/{n:,} = **{hit/n:.1%}**   活性 {active:,}/{n:,} = {active/n:.1%}"
          f"   耗时 {time.time()-t0:.1f}s{extra}")
