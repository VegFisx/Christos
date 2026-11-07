# -*- coding: utf-8 -*-
r"""★ 关键复测：**把"非贡献组分"当试剂填进条件**之后，氧化还原门控是否终于转正？

第二十四轮的门控净亏（命中 13.2% -> 4.1%），根因是"试剂可得率 0%"。
本轮的发现：**试剂一直在**——ORD 记录里"不贡献原子到产物"的那些组分就是试剂
（实测单底物记录 81.6% 有它们；Top：`[Na+]`/`[OH-]`/`[H-]`/`[BH4-]`/`[H][H]`/`[Al+3]`/TFA/AcOH/Et3N）。

四配置：
  A 单底物模板关
  B 模板开 + 门控关
  C 模板开 + 门控开 + 条件【不带试剂】（第二十四轮的做法，预期仍净亏）
  D 模板开 + 门控开 + 条件【带试剂】（本轮做法，预期转正）
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
    pm = mc.parse_plain(str(rhs))
    if pm is None:
        skip["产物非法"] += 1
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        skip["产物无映射"] += 1
        continue
    contrib, noncontrib = [], []
    for p in [x for x in str(lhs or "").split(".") if x]:
        m = mc.parse_plain(p)
        if m is None:
            continue
        nums = mc.map_nums(m)
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            contrib.append(p)
        else:
            noncontrib.append(p)
    if len(contrib) != 1:
        skip[f"贡献组分={len(contrib)}"] += 1
        continue
    cs = mc.canon_plain(contrib[0])
    if not cs:
        skip["底物归一失败"] += 1
        continue
    wants = {mc.canon_plain(x) for x in str(rhs).split(".") if x.strip()}
    wants.discard(None)
    reagents = tuple(x for x in (mc.canon_plain(p) for p in noncontrib) if x)
    cases.append((cs, wants, temp, solv, reagents))
    if len(cases) >= MAX_MONO:
        break

n_with_reagent = sum(1 for c in cases if c[4])
from smartreact_engine import REDUCTANT_HINTS, OXIDANT_HINTS  # noqa: E402
n_red = sum(1 for c in cases if any(h in " ".join(c[4]) for h in REDUCTANT_HINTS))
n_oxi = sum(1 for c in cases if any(h in " ".join(c[4]) for h in OXIDANT_HINTS))
print("=" * 100)
print(f"带试剂的复测：单底物记录 {len(cases):,} 条（抽样 {N:,}）")
print(f"  其中【带非贡献组分(=试剂)】的 {n_with_reagent:,} = {n_with_reagent/max(1,len(cases)):.1%}")
print(f"  其中【被 REDUCTANT_HINTS 识别出还原剂】的 {n_red:,} = {n_red/max(1,len(cases)):.1%}"
      f"    【识别出氧化剂】的 {n_oxi:,} = {n_oxi/max(1,len(cases)):.1%}")
print(f"  → 识别率就是门控的天花板：识别不到的记录，还原模板仍会被挡")
print(f"  跳过：{dict(skip)}")
print("=" * 100)


def cond_of(temp, solv, reagents, with_reagents):
    s = str(solv or "").lower()
    sol = "water" if ("water" in s or "h2o" in s) else (s.split(";")[0].split(",")[0].strip() or "water")
    t = float(temp) if temp is not None and temp == temp else 100.0
    return M.Conditions(solvent=sol, temperature=t, time_min=60.0, atmosphere="air",
                        reagents=tuple(reagents) if with_reagents else ())


CONFIGS = [
    ("A 模板关", dict(use_mono_templates=False), False, False),
    ("B 模板开 + 门控关", dict(use_mono_templates=True, mono_redox_gate=False), False, False),
    ("C 模板开 + 门控开 + 无试剂", dict(use_mono_templates=True, mono_redox_gate=True), True, False),
    ("D 模板开 + 门控开 + 带试剂", dict(use_mono_templates=True, mono_redox_gate=True), True, True),
]
for label, kw, use_cond, with_reagents in CONFIGS:
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False, **kw)
    hit = active = 0
    for smi, wants, temp, solv, reagents in cases:
        cond = cond_of(temp, solv, reagents, with_reagents) if use_cond else None
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
    g = {k: v for k, v in eng.gate_stats.items() if "单底物" in k}
    print(f"\n[{label}]")
    print(f"  命中 {hit:,}/{n:,} = **{hit/n:.1%}**   活性 {active:,}/{n:,} = {active/n:.1%}"
          f"   耗时 {time.time()-t0:.1f}s" + (f"   门控 {g}" if g else ""))
