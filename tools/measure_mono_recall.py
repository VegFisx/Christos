# -*- coding: utf-8 -*-
r"""收益测量：单底物模板让【真实单底物反应】的产物命中率提升多少？

口径：
  · 抽样：ORD 全量 duckdb reservoir（固定 seed），只取 **贡献组分 = 1** 的记录（单底物）
  · 对每条：用那个唯一底物跑 `engine.step([底物], cond=None)`（cond=None -> 不做条件门控，隔离模板效果）
  · 命中判定：记录产物（CXSMILES 右侧，点号拆开）**任一组分**出现在引擎输出里
  · 对比：use_mono_templates=False（旧）vs True（新）
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
from ord_schema.proto import reaction_pb2  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402
from engine import Compound  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BIG = STAGE / "ord-data" / "data" / "11" / \
    "ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000
SEED = 20261012
MAX_MONO = 2000

con = duckdb.connect()
rows = con.execute(f"""
    SELECT reaction FROM read_parquet('{BIG.as_posix()}')
    USING SAMPLE {N} ROWS (reservoir, {SEED})
""").fetchall()

# ---- 先挑出单底物记录 ----
cases = []
skip = Counter()
for (blob,) in rows:
    try:
        rxn = reaction_pb2.Reaction()
        rxn.ParseFromString(bytes(blob))
    except Exception:
        skip["protobuf"] += 1
        continue
    cx = next((i.value for i in rxn.identifiers
               if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value), None)
    if not cx:
        skip["无CXSMILES"] += 1
        continue
    lhs, _agents, rhs = mc.split_rxn(cx)
    pm = mc.parse_plain(rhs)
    if pm is None:
        skip["产物非法"] += 1
        continue
    pmaps = mc.map_nums(pm)
    if not pmaps:
        skip["产物无映射"] += 1
        continue
    raws, plains = mc.contributing_components(lhs, pmaps)
    if len(plains) != 1:
        skip[f"贡献组分={len(plains)}"] += 1
        continue
    wants = [mc.canon_plain(x) for x in rhs.split(".") if x.strip()]
    wants = [w for w in wants if w]
    if not wants:
        skip["产物归一失败"] += 1
        continue
    cases.append((plains[0], set(wants)))
    if len(cases) >= MAX_MONO:
        break

print("=" * 100)
print(f"单底物模板的收益测量：单底物记录 {len(cases):,} 条（抽样 {N:,}，seed {SEED}）")
print(f"  跳过：{dict(skip)}")
print("=" * 100)

from smartreact_engine import SmartReactEngine  # noqa: E402

for mono in (False, True):
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False,
                           use_mono_templates=mono, verbose=False)
    hit = active = 0
    fail = 0
    for smi, wants in cases:
        try:
            prods = eng.step([Compound(smiles=smi, name="x", herb="ord")], None, round_no=1)
        except Exception:
            fail += 1
            continue
        got = {mc.canon_plain(p.smiles) for p in prods}
        got.discard(None)
        if got:
            active += 1
        if wants & got:
            hit += 1
    n = max(1, len(cases))
    print(f"\n[use_mono_templates={mono}]  {eng.mono_template_note}")
    print(f"  命中记录产物 {hit:,}/{n:,} = **{hit/n:.1%}**   "
          f"有产物(活性) {active:,} = {active/n:.1%}   异常 {fail}   耗时 {time.time()-t0:.1f}s")
