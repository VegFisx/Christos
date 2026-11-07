#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A10~A13 自检：cascade / thermo 的数值常数必须登记、且与代码里读到的值一致。

跑法：
    python -I tools\\test_constants_provenance.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "conditions", ROOT / "rules"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

REG = json.loads((ROOT / "core" / "constants_provenance.json").read_text(encoding="utf-8"))
CONSTS = REG.get("constants") or {}
STATUSES = set((REG.get("status_vocabulary") or {}).keys())
EFFECTS = set((REG.get("gate_effect_vocabulary") or {}).keys())
fails = []


def check(cond, msg):
    print(("  PASS  " if cond else "  FAIL  ") + msg)
    if not cond:
        fails.append(msg)


print("== 1. 覆盖与词表 ==")
check(len(CONSTS) == 8, "登记 8 个常数（实际 %d）" % len(CONSTS))
bad = [k for k, v in CONSTS.items() if v.get("status") not in STATUSES]
check(not bad, "status 都在词表内 %s" % (bad or ""))
bad = [k for k, v in CONSTS.items() if v.get("gate_effect") not in EFFECTS]
check(not bad, "gate_effect 都在词表内 %s" % (bad or ""))
miss = [k for k, v in CONSTS.items()
        if not (v.get("note") and v.get("policy") and v.get("used_by"))]
check(not miss, "每个常数都有 note/policy/used_by %s" % (miss or ""))

print("== 2. 标 literature 就必须有引文 ==")
bad = [k for k, v in CONSTS.items() if v.get("status") == "literature" and not v.get("evidence")]
check(not bad, "literature 项都有 evidence %s" % (bad or ""))

print("== 3. 会影响产物集合的常数必须写明证据或理由 ==")
bad = [k for k, v in CONSTS.items()
       if v.get("gate_effect") == "stops_propagation" and not v.get("evidence")]
check(not bad, "stops_propagation 项都有 evidence %s" % (bad or ""))
mp = CONSTS.get("cascade.min_propagate_score") or {}
scan = ((mp.get("evidence") or {}).get("scan") or [])
check(len(scan) == 4, "传播门槛的扫描表 4 行（实际 %d）" % len(scan))

print("== 4. 代码里读到的值 == 登记值 ==")
import cascade as C                                # noqa: E402
import thermo as TH                                # noqa: E402

pairs = [("cascade.round_decay", C.ROUND_DECAY),
         ("cascade.min_thermo_coverage", C.MIN_THERMO_COVERAGE),
         ("cascade.min_propagate_score", C.MIN_PROPAGATE_SCORE),
         ("thermo.dg_favorable", TH.DG_FAVORABLE),
         ("thermo.dg_unfavorable", TH.DG_UNFAVORABLE),
         ("thermo.max_heavy_for_xtb", TH.MAX_HEAVY_FOR_XTB),
         ("thermo.dg_sane_min", TH.DG_SANE_MIN),
         ("thermo.dg_sane_max", TH.DG_SANE_MAX)]
drift = [(k, v, CONSTS[k]["value"]) for k, v in pairs if v != CONSTS[k]["value"]]
check(not drift, "无漂移 %s" % (drift or ""))
print("   实际值：" + ", ".join("%s=%s" % (k.split(".")[1], v) for k, v in pairs))

print("")
if fails:
    print("FAILED %d 项" % len(fails))
    raise SystemExit(1)
print("ALL PASS（4 组检查）")
