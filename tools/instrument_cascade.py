# -*- coding: utf-8 -*-
r"""给 cascade 内部的每一次 engine.step 装计时器，定位那 20 分钟到底花在哪。"""
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

from cascade import cascade, MIN_PROPAGATE_SCORE      # noqa: E402
from smartreact_engine import SmartReactEngine        # noqa: E402
from engine import get_mol                            # noqa: E402
import templates as T                                 # noqa: E402
from herb import compounds_of_herb                    # noqa: E402

import argparse  # noqa: E402
ap = argparse.ArgumentParser()
ap.add_argument("--medium-rev", choices=["on", "off"], default="on")
ap.add_argument("--max-rounds", type=int, default=6)
A = ap.parse_args()
MED = (A.medium_rev == "on")

seeds = compounds_of_herb("甘草", limit=6)
cond = T.get_template("煎煮")
print("=" * 96, flush=True)
print(f"仪器化级联：甘草 {len(seeds)} 成分 / 煎煮 / frontier 6 / "
      f"max_rounds {A.max_rounds} / min_new 3 / 介质可逆性={A.medium_rev}", flush=True)
print("=" * 96, flush=True)


def ha_stats(smiles_list):
    hs = []
    for s in smiles_list:
        m = get_mol(s)
        if m is not None:
            hs.append(m.GetNumHeavyAtoms())
    if not hs:
        return (0, 0, 0)
    return (len(hs), sum(hs) / len(hs), max(hs))


for label, kw in (("A 自抽模板关", dict(use_extra_templates=False,
                                        medium_aware_reversibility=MED)),
                  ("B 默认（K1 开）", dict(medium_aware_reversibility=MED))):
    e = SmartReactEngine(gate_conditions=True, **kw)
    calls = []
    orig = e.step

    def timed(*a, **k):
        n_in = len(a[0]) if a else -1
        hin = ha_stats([c.smiles for c in a[0]]) if a else (0, 0, 0)
        t0 = time.time()
        out = orig(*a, **k)
        dt = time.time() - t0
        hout = ha_stats([p.smiles for p in out])
        calls.append((n_in, len(out), dt))
        print(f"    step: 底物 {n_in:>3}（重原子 均{hin[1]:>5.1f}/max{hin[2]:>3}）"
              f" → 产物 {len(out):>4}（重原子 均{hout[1]:>5.1f}/max{hout[2]:>3}）"
              f"  耗时 {dt:>8.2f}s", flush=True)
        return out

    e.step = timed
    t0 = time.time()
    r = cascade(e, seeds, cond, max_rounds=A.max_rounds, min_new=3, frontier_limit=6,
                min_propagate_score=MIN_PROPAGATE_SCORE)
    dt = time.time() - t0
    t_steps = sum(c[2] for c in calls)
    print(f"\n  [{label}] 收敛={'是' if r.converged else '否'}  轮数={r.rounds}  "
          f"产物={r.total}  总耗时={dt:.1f}s", flush=True)
    print(f"    step 合计 {t_steps:.1f}s（{len(calls)} 次）；"
          f"非 step 开销 {dt-t_steps:.1f}s（打分/采样/排序/收尾）", flush=True)
    print(f"    {'轮':>3}{'新增':>7}{'可传播':>8}{'被拦':>7}", flush=True)
    for s in r.round_stats:
        print(f"    {s['round']:>3}{s['new']:>7}{s['irreversible_new']:>8}"
              f"{s.get('below_floor', 0):>7}", flush=True)
    print(flush=True)
