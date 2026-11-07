# -*- coding: utf-8 -*-
r"""验证第十九轮的「介质相关可逆性」：水相里脱水缩合判为可逆，醇相里不判。"""
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

from smartreact_engine import SmartReactEngine, CONDENSATION_CLASSES   # noqa: E402
import model as M                                                      # noqa: E402
import templates as T                                                  # noqa: E402
from herb import compounds_of_herb                                     # noqa: E402

seeds = compounds_of_herb("甘草", limit=6)
print("=" * 96)
print(f"介质相关可逆性验证（CONDENSATION_CLASSES 共 {len(CONDENSATION_CLASSES)} 类）")
print(f"  {' '.join(sorted(CONDENSATION_CLASSES))}")
print("=" * 96)

CASES = [
    ("水相 煎煮 / 可逆性【开】= 默认", T.get_template("煎煮"), dict()),
    ("水相 煎煮 / 可逆性【关】= 旧行为", T.get_template("煎煮"),
     dict(medium_aware_reversibility=False)),
    ("醇相 乙醇回流 / 默认", M.Conditions(solvent="ethanol", temperature=78.0, time_min=60.0),
     dict()),
]
for label, cond, kw in CASES:
    e = SmartReactEngine(gate_conditions=True, use_extra_templates=False, **kw)
    t0 = time.time()
    pr = e.step(seeds, cond, 0.15, round_no=1)
    dt = time.time() - t0
    rev = sum(1 for p in pr if p.reversible)
    print(f"\n[{label}]  条件={cond.describe()}")
    print(f"  产物 {len(pr)}   标记可逆 {rev}   耗时 {dt:.2f}s   "
          f"stats.reversible_by_medium={e.stats.get('reversible_by_medium')}")
    by = {}
    for p in pr:
        if p.reversible:
            by[p.rule_name] = by.get(p.rule_name, 0) + 1
    if by:
        print(f"    可逆产物按类型：{dict(sorted(by.items(), key=lambda kv: -kv[1]))}")

print("\n★ 期望：水相 开 -> rev>0；水相 关 -> rev=0；醇相 -> rev=0（保住'醇提=酯交换'那条化学）")
