# -*- coding: utf-8 -*-
r"""重验收敛：**当前引擎（SmartReact + 第十六轮起默认开的 590 条自抽模板）还收敛吗？**

## 为什么必须重验
ROUND12 解决过"级联不收敛"：诊断出根因是**传播门槛太低**，解法是**按分数设门槛**
（`core/cascade.py::MIN_PROPAGATE_SCORE = 0.35`）→ 当时实测 **7 轮收敛、高分产物 573 个一个不丢**；ROUND13 在真实工艺上复验。
**但那是在旧引擎（63 条手写规则）上验的。** 现在：
  · 引擎换成了 SmartReact（9,770 模板 / 37 类）
  · 第十六轮起 **590 条 ORD 自抽模板默认打开**，而且它们的 `rule_name = "mined_extra"`
    ——**不在引擎的 37 条规则表里**，打分时 `rule_match` 取不到对应规则
  · 已知副作用：自抽模板**完全绕过条件门控**

→ 所以「收敛」这个结论**必须在新配置上重新测**，不能沿用。

## 口径（与 ROUND12/`verify_convergence.py` 逐字一致，才可比）
  底物：甘草 15 个成分（`sources/herb.py::compounds_of_herb`，来自 tcm.db）
  条件：煎煮（`conditions/templates.py::get_template`）
  调用：`cascade(..., max_rounds=8, min_new=10, frontier_limit=40, min_propagate_score=0.35)`
  对比：A=自抽模板关（旧配置）  B=默认（K1 开，590 条）

跑法：& "D:\TCMAI\venv\Scripts\python.exe" tools\check_convergence_current.py
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
from smartreact_engine import SmartReactEngine            # noqa: E402
import templates as T                                     # noqa: E402
from herb import compounds_of_herb                        # noqa: E402

# ★ CLI：口径可调（frontier_limit=40 时配 K1 开要小时级，故默认收到 12 —— 记录清楚）
import argparse  # noqa: E402
ap = argparse.ArgumentParser()
ap.add_argument("--frontier", type=int, default=12)
ap.add_argument("--max-rounds", type=int, default=8)
ap.add_argument("--min-new", type=int, default=10)
ap.add_argument("--out", default=str(STAGE / "reports" / "convergence_recheck.json"))
A = ap.parse_args()

seeds = compounds_of_herb("甘草", limit=15)
cond = T.get_template("煎煮")
print("=" * 100, flush=True)
print("重验收敛：当前引擎下，级联还收不收敛？（同 ROUND12 口径，frontier 见下）", flush=True)
print("=" * 100, flush=True)
print(f"  底物：甘草 {len(seeds)} 个成分    条件：{cond.describe()}", flush=True)
print(f"  传播门槛 MIN_PROPAGATE_SCORE = {MIN_PROPAGATE_SCORE}"
      f"    max_rounds={A.max_rounds}  min_new={A.min_new}  frontier_limit={A.frontier}", flush=True)

CFGS = [("A 自抽模板关（ROUND12 时的等价配置）", dict(use_extra_templates=False)),
        ("B 默认（K1 开，590 条自抽模板）", dict())]

summary = {}
for label, kw in CFGS:
    t0 = time.time()
    eng = SmartReactEngine(gate_conditions=True, **kw)
    print("\n" + "=" * 100)
    print(f"[{label}]  额外模板：{eng.extra_template_note}")
    print("=" * 100)
    try:
        r = cascade(eng, seeds, cond, max_rounds=A.max_rounds, min_new=A.min_new,
                    frontier_limit=A.frontier, min_propagate_score=MIN_PROPAGATE_SCORE)
    except Exception as e:
        print(f"  ❌ cascade 抛异常：{type(e).__name__}: {e}", flush=True)
        summary[label] = {"error": f"{type(e).__name__}: {e}"}
        continue
    hi = [p for p in r.products if not p.is_byproduct and p.score >= 0.5]
    mined = [p for p in r.products if getattr(p, "rule_name", "") == "mined_extra"]
    print(f"  收敛：{'✅ 是' if r.converged else '❌ 否'}   跑了 {r.rounds} 轮   "
          f"产物总数 {r.total}   高分(>=0.5) {len(hi)}   耗时 {time.time()-t0:.1f}s", flush=True)
    print(f"  其中 mined_extra 产物 {len(mined)} 个"
          + (f"（最高分 {max(p.score for p in mined):.3f}）" if mined else ""), flush=True)
    print(f"\n  {'轮':>3}{'新增':>7}{'可传播':>8}{'低于门槛被拦':>13}{'累计':>8}", flush=True)
    cum = 0
    for s in r.round_stats:
        cum += s["new"]
        print(f"  {s['round']:>3}{s['new']:>7}{s['irreversible_new']:>8}"
              f"{s.get('below_floor', 0):>13}{cum:>8}", flush=True)
    summary[label] = {"converged": bool(r.converged), "rounds": int(r.rounds),
                      "total": int(r.total), "high_score": len(hi),
                      "mined_extra": len(mined),
                      "seconds": round(time.time() - t0, 1),
                      "per_round": r.round_stats}
    # ★ 逐配置落盘：这样即使后一个配置跑很久，前一个的结论已经保住了
    Path(A.out).write_text(json.dumps(
        {"seeds": "甘草 15 成分", "cond": cond.describe(), "floor": MIN_PROPAGATE_SCORE,
         "frontier_limit": A.frontier, "max_rounds": A.max_rounds, "min_new": A.min_new,
         "summary": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  （已落盘 {Path(A.out).name}）", flush=True)

print("\n" + "=" * 100, flush=True)
print("对比", flush=True)
print("=" * 100, flush=True)
ks = [k for k, v in summary.items() if "error" not in v]
for k in ks:
    v = summary[k]
    print(f"  {k:<40} 收敛={v['converged']}  轮数={v['rounds']}  "
          f"产物={v['total']}  高分={v['high_score']}  "
          f"mined_extra={v['mined_extra']}  {v['seconds']}s", flush=True)
if len(ks) == 2:
    a, b = summary[ks[0]], summary[ks[1]]
    print(f"\n  ★ 开自抽模板带来的变化：产物 {a['total']} → {b['total']} "
          f"({b['total']-a['total']:+d})；高分 {a['high_score']} → {b['high_score']} "
          f"({b['high_score']-a['high_score']:+d})；收敛 {a['converged']} → {b['converged']}",
          flush=True)

import json  # noqa: E402
Path(A.out).write_text(json.dumps(
    {"seeds": "甘草 15 成分", "cond": cond.describe(), "floor": MIN_PROPAGATE_SCORE,
     "frontier_limit": A.frontier, "max_rounds": A.max_rounds, "min_new": A.min_new,
     "summary": summary}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n-> {Path(A.out).name}", flush=True)
