# -*- coding: utf-8 -*-
"""检查 conditions/kinetics_measurements.json 的出处完整性（AGENTS §十二）。

不测化学，只测「每条实测数据都能追到文献」：
1. 每条有 source.doi 或 source.url；
2. 每条有 quote（原文引句）；
3. 有 times_min 就有同长度 conversion；有 k_per_h 就不该再有 times_min；
4. 转化率都在 (0,1) 开区间（0 与 1 不入拟合，写了也没用）；
5. kinetics.json 的 q10.value 与 train_calibration 存在且 value 仍是 2.0（改默认值必须显式拍板）。

用法：python -I tools/test_kinetics_measurements.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                      # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
MEAS = ROOT / "conditions" / "kinetics_measurements.json"
KIN = ROOT / "conditions" / "kinetics.json"

fails = 0


def check(cond: bool, msg: str) -> None:
    global fails
    print(("  [PASS] " if cond else "  [FAIL] ") + msg)
    if not cond:
        fails += 1


def main() -> int:
    data = json.loads(MEAS.read_text(encoding="utf-8"))
    sets = data.get("datasets") or []
    check(len(sets) >= 3, "数据集数量 %d >= 3" % len(sets))

    bad_src = [d["id"] for d in sets
               if not ((d.get("source") or {}).get("doi")
                       or (d.get("source") or {}).get("url"))]
    check(not bad_src, "每条都有 DOI/URL（缺：%s）" % (bad_src or "无"))

    bad_quote = [d["id"] for d in sets if not (d.get("source") or {}).get("quote")]
    check(not bad_quote, "每条都有原文引句（缺：%s）" % (bad_quote or "无"))

    bad_len = [d["id"] for d in sets
               if d.get("times_min") and len(d["times_min"]) != len(d.get("conversion") or [])]
    check(not bad_len, "times_min 与 conversion 等长（坏：%s）" % (bad_len or "无"))

    mixed = [d["id"] for d in sets if d.get("times_min") and d.get("k_per_h")]
    check(not mixed, "同一条不同时给时间序列和已报告 k（坏：%s）" % (mixed or "无"))

    bad_conv = [d["id"] for d in sets for y in (d.get("conversion") or [])
                if not (0.0 < float(y) < 1.0)]
    check(not bad_conv, "转化率都在 (0,1) 开区间（坏：%s）" % (bad_conv or "无"))

    kin = json.loads(KIN.read_text(encoding="utf-8"))
    q10 = kin.get("q10") or {}
    check(q10.get("value") == 2.0, "q10.value 仍为 2.0（未擅自改默认值）")
    check(bool(q10.get("train_calibration")), "q10.train_calibration 已登记实测")

    print("TEST %s" % ("ALL PASS" if not fails else "FAILED %d" % fails))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
