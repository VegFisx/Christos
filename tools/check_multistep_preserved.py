# -*- coding: utf-8 -*-
r"""验证第十九轮修复的**副作用边界**：不能把"多步预测"整个关掉。

期望（设计意图）：
  · 水相 + 甘草：37 类只出缩合产物（酯化）+ mined_extra -> 无可传播 -> **1 轮**（这是对的，水里没有可驱动的多步）
  · **醇相**（乙醇回流）：酯交换是被驱动的（ROUND7 实测"酯交换 = 醇提的化学实质"）-> **应当 >1 轮**
  · 引擎自带自检（水杨酸/酪胺/甘油/苯硼酸/对羟基苯乙酮，水相）：看还有没有多步
"""
from __future__ import annotations

import sys
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
from engine import Compound                           # noqa: E402
import model as M                                     # noqa: E402
import templates as T                                 # noqa: E402
from herb import compounds_of_herb                    # noqa: E402

print("=" * 96)
print("副作用边界检查：多步预测还在不在？")
print("=" * 96)


def run(label, seeds, cond, **kw):
    e = SmartReactEngine(gate_conditions=True, **kw)
    r = cascade(e, seeds, cond, max_rounds=4, min_new=3, frontier_limit=6,
                min_propagate_score=MIN_PROPAGATE_SCORE)
    print(f"\n[{label}]")
    print(f"  收敛={'是' if r.converged else '否'}  轮数={r.rounds}  产物={r.total}")
    for s in r.round_stats:
        print(f"    第{s['round']}轮  新增 {s['new']:>4}  可传播 {s['irreversible_new']:>4}"
              f"  低于门槛 {s.get('below_floor', 0):>4}")
    return r


g6 = compounds_of_herb("甘草", limit=6)
run("甘草 6 成分 / 水相煎煮（期望 1 轮：水里没有可驱动的多步）", g6, T.get_template("煎煮"),
    use_extra_templates=False)
run("甘草 6 成分 / 醇相乙醇回流（期望 >1 轮：酯交换被驱动）", g6,
    M.Conditions(solvent="ethanol", temperature=78.0, time_min=60.0), use_extra_templates=False)

selftest = [Compound(smiles=s, name=n, herb="selftest") for s, n in [
    ("O=C(O)c1ccccc1O", "水杨酸"),
    ("NCCc1ccc(O)cc1", "酪胺"),
    ("OCC(O)CO", "甘油"),
    ("c1ccc(B(O)O)cc1", "苯硼酸"),
    ("CC(=O)c1ccc(O)cc1", "对羟基苯乙酮"),
]]
run("引擎自检底物 5 个 / 水相 100℃（看还有没有多步）", selftest,
    M.Conditions(solvent="water", temperature=100.0, time_min=60.0), use_extra_templates=False)

print("\n★ 读法：水相 1 轮是**设计预期**（缩合不该在水里驱动多步）；"
      "醇相/自检若 >1 轮，说明多步能力没被关掉。")
