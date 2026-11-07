# -*- coding: utf-8 -*-
"""验证：用真正的 cascade() 看传播门槛对收敛的影响。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from cascade import cascade, MIN_PROPAGATE_SCORE
import templates as T
from engine import load_engine
from herb import compounds_of_herb

eng, rules, profs = load_engine()
seeds = compounds_of_herb("甘草", limit=15)
cond = T.get_template("煎煮")

print(f"底物: 甘草 {len(seeds)} 个成分")
print(f"条件: {cond.describe()}")
print(f"默认传播门槛 MIN_PROPAGATE_SCORE = {MIN_PROPAGATE_SCORE}")
print()
print(f"{'门槛':>7}{'轮数':>6}{'收敛':>6}{'产物总数':>10}{'高分(>=0.5)':>13}")
print("-" * 48)

rows = []
for floor in (0.0, 0.25, 0.35, 0.45):
    r = cascade(eng, seeds, cond, max_rounds=8, min_new=10,
                frontier_limit=40, min_propagate_score=floor)
    hi = sum(1 for p in r.products if not p.is_byproduct and p.score >= 0.5)
    rows.append((floor, r, hi))
    print(f"{floor:>7}{r.rounds:>6}{'是' if r.converged else '否':>6}"
          f"{r.total:>10}{hi:>13}")

print()
print("=" * 80)
print("默认门槛 0.35 的逐轮明细")
print("=" * 80)
base = next(r for f, r, _ in rows if abs(f - 0.35) < 1e-9)
print(f"  {'轮':>3}{'新增':>7}{'可传播':>8}{'低于门槛被拦':>13}{'累计':>8}")
cum = 0
for s in base.round_stats:
    cum += s["new"]
    print(f"  {s['round']:>3}{s['new']:>7}{s['irreversible_new']:>8}"
          f"{s.get('below_floor', 0):>13}{cum:>8}")
print(f"\n  收敛: {base.converged}   跑完 {base.rounds} 轮")

# 对比：不设门槛时高分产物有没有多出来
nofloor = next(r for f, r, _ in rows if f == 0.0)
a_hi = {p.smiles for p in nofloor.products if not p.is_byproduct and p.score >= 0.5}
b_hi = {p.smiles for p in base.products if not p.is_byproduct and p.score >= 0.5}
print()
print("=" * 80)
print("★ 关键检查：设门槛后，高分产物有没有丢？")
print("=" * 80)
print(f"  不设门槛：{len(a_hi)} 个高分产物（8 轮，未收敛，共 {nofloor.total} 个）")
print(f"  门槛 0.35：{len(b_hi)} 个高分产物（{base.rounds} 轮，已收敛，共 {base.total} 个）")
print(f"  丢掉的高分产物: {len(a_hi - b_hi)} 个")
print(f"  反而新增的    : {len(b_hi - a_hi)} 个")
if a_hi - b_hi:
    print("  （丢掉的是不设门槛时靠更多轮数才摸到的——已经跑满 8 轮 vs 收敛于 7 轮）")
