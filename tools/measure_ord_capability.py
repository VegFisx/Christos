# -*- coding: utf-8 -*-
r"""★ 新口径下的能力基线：把试剂接进条件后，"我们现在到底几斤几两"。

口径（全部经 `tools/ord_conditions.py`，单一真相）：
  · 用例：ORD 分片抽样里**恰好 2 个贡献组分**的记录（引擎能尝试的那批）
  · 条件：记录自己的温度/溶剂（缺失温度按 100 ℃，**不填 0**）；气氛 air；试剂可开关
  · 命中：记录产物（点号拆开后任一组分）出现在引擎输出里

四配置（逐项叠加，隔离每一块贡献）：
  A 旧口径基线：无试剂 + 自抽模板关 + 单底物模板关        （= 第十七轮那套数字的口径）
  B A + 真实共试剂                                         （第二十六轮接上的东西）
  C B + ORD 自抽双底物模板（K1，当前默认开）
  D C + ORD 自抽单底物模板（当前完整默认）
"""
from __future__ import annotations

import sys
import time
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

from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402
from engine import Compound  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402
from ord_conditions import load_ord_cases, build_conditions  # noqa: E402

RDLogger.DisableLog("rdApp.*")

CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
cases, skip = load_ord_cases(n=60000, need_contrib=2, cap=CAP)
n_reag = sum(1 for c in cases if c["reagents"])
print("=" * 100)
print(f"新口径能力基线：用例 {len(cases):,}（恰好 2 个贡献组分）")
print(f"  其中带真实共试剂的 {n_reag:,} = {n_reag/max(1,len(cases)):.1%}")
print(f"  跳过：{skip}")
print("=" * 100)

CONFIGS = [
    ("A 旧口径：无试剂 + 自抽关 + 单底物关", False, False, False),
    ("B A + 真实共试剂", True, False, False),
    ("C B + ORD 自抽双底物模板(K1)", True, True, False),
    ("D C + ORD 自抽单底物模板(完整默认)", True, True, True),
]
print(f"\n{'配置':<40}{'命中':>9}{'活性':>8}{'门控判零':>10}{'产物/条':>9}{'耗时':>8}")
rows = []
for label, with_reag, extra, mono in CONFIGS:
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, use_extra_templates=extra,
                           use_mono_templates=mono, verbose=False)
    hit = active = nprod = gz = 0
    for c in cases:
        cond = build_conditions(c["temperature_C"], c["solvent_names"],
                                ";".join(c["reagents"]), with_reagents=with_reag)
        comps = [Compound(smiles=s, name="x", herb="ord") for s in c["substrates"]]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception:
            continue
        got = {mc.canon_plain(p.smiles) for p in prods}
        got.discard(None)
        nprod += len(got)
        if got:
            active += 1
        if c["wants"] & got:
            hit += 1
        gz += eng.stats.get("gated_zero_total", 0)
    n = max(1, len(cases))
    dt = time.time() - t0
    print(f"{label:<40}{hit/n:>8.1%}{active/n:>8.1%}{gz:>10,}{nprod/n:>9.2f}{dt:>7.1f}s")
    rows.append({"config": label, "hit": hit / n, "active": active / n,
                 "gated_zero": gz, "products_per_case": nprod / n, "seconds": round(dt, 1)})

import json  # noqa: E402
out = STAGE / "reports" / "ord_capability_baseline.json"
out.write_text(json.dumps({
    "scratch": "新口径（带真实共试剂）下的能力基线；口径经 tools/ord_conditions.py",
    "n_cases": len(cases), "n_with_reagents": n_reag, "skip": skip, "rows": rows,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {out.name}")
