# -*- coding: utf-8 -*-
r"""级联收敛（小配置）+ 定位真正的耗时点。

背景：frontier=12 / K1 关的配置实测跑了 20+ 分钟没出结果，而**引擎单步只要 1.91s**（15 底物/105 对/654 产物）。
→ 怀疑瓶颈在 **逐个产物打分 `score_product`**，不在模板枚举。本脚本两件事一起做：
  ① 给 score_product 计时（回答"慢在哪"）
  ② 用小配置（6 底物 / frontier 6 / 6 轮）把「还收不收敛」这个结论拿到
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
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cascade import cascade, MIN_PROPAGATE_SCORE          # noqa: E402
from scorer import score_product                          # noqa: E402
from smartreact_engine import SmartReactEngine            # noqa: E402
import templates as T                                     # noqa: E402
from herb import compounds_of_herb                        # noqa: E402

seeds = compounds_of_herb("甘草", limit=6)
cond = T.get_template("煎煮")
print("=" * 100, flush=True)
print("① 定位瓶颈：给 score_product 计时", flush=True)
print("=" * 100, flush=True)
eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False, verbose=False)
t0 = time.time()
prods = eng.step(seeds, cond, 0.15, round_no=1)
t_step = time.time() - t0
print(f"  引擎单步：底物 {len(seeds)}  产物 {len(prods)}  耗时 {t_step:.2f}s  "
      f"({t_step/max(1,len(prods))*1000:.1f} ms/产物)", flush=True)

rule_by_id = eng._rule_by_id
t0 = time.time()
for p in prods:
    score_product(p.smiles, rule_by_id.get(p.rule_id, {}), 1.0, source_smiles=p.source_smiles)
t_sc = time.time() - t0
print(f"  逐个打分 {len(prods)} 个产物：{t_sc:.2f}s  "
      f"({t_sc/max(1,len(prods))*1000:.1f} ms/产物)  ← 看这个是不是瓶颈", flush=True)
print(f"  → 单步枚举 {t_step:.2f}s vs 打分 {t_sc:.2f}s；"
      f"打分占 {t_sc/(t_step+t_sc):.0%}", flush=True)

print("\n" + "=" * 100, flush=True)
print("② 小配置下的收敛（6 底物 / frontier 6 / max_rounds 6 / min_new 3）", flush=True)
print("=" * 100, flush=True)
for label, kw in (("A 自抽模板关", dict(use_extra_templates=False)),
                  ("B 默认（K1 开）", dict())):
    e = SmartReactEngine(gate_conditions=True, **kw)
    t0 = time.time()
    r = cascade(e, seeds, cond, max_rounds=6, min_new=3, frontier_limit=6,
                min_propagate_score=MIN_PROPAGATE_SCORE)
    dt = time.time() - t0
    hi = sum(1 for p in r.products if not p.is_byproduct and p.score >= 0.5)
    print(f"\n  [{label}] 收敛={'✅ 是' if r.converged else '❌ 否'}  "
          f"轮数={r.rounds}  产物={r.total}  高分={hi}  耗时={dt:.1f}s", flush=True)
    print(f"    {'轮':>3}{'新增':>7}{'可传播':>8}{'被拦':>7}{'累计':>8}", flush=True)
    cum = 0
    for s in r.round_stats:
        cum += s["new"]
        print(f"    {s['round']:>3}{s['new']:>7}{s['irreversible_new']:>8}"
              f"{s.get('below_floor', 0):>7}{cum:>8}", flush=True)
