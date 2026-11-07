# -*- coding: utf-8 -*-
"""把实测标定结果写进 conditions/kinetics.json 的 q10.train_calibration（幂等）。

只做三件事：
1. 读 reports/kinetics_calibration_20261106.json（由 tools/fit_extent_kinetics.py 产出）；
2. 在 kinetics.json 的 q10 下追加 train_calibration 块（实测 Q10、来源、是否改默认值的判断）；
3. 不改 q10.value —— 改默认值需要用户拍板（AGENTS §十二）。

用法：
    python -I tools/land_kinetics_calibration.py           # 写入
    python -I tools/land_kinetics_calibration.py --dry     # 只看结果
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                      # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "reports" / "kinetics_calibration_20261106.json"
KIN = ROOT / "conditions" / "kinetics.json"

# 每条实测只保留「反应 / 温度 / Q10 / Ea / 来源 DOI」，不复制原始表格
SOURCES = {
    "hydrolysis_glycoside_rb1": {
        "title": "Conversion of Ginsenosides by High Temperature and Pressure Processing",
        "journal": "J Pharmacopuncture",
        "year": 2020,
        "doi": "10.3831/KPI.2020.23.012",
        "matrix": "水/蒸汽（105/94/80 °C），三种温度长时程",
    },
    "hydrolysis_glycoside_rb1_lit2015": {
        "title": "Kinetic study for the optimization of ginsenoside Rg3 production by heat treatment of ginsenoside Rb1",
        "journal": "J Ginseng Res",
        "year": 2015,
        "doi": "10.1016/j.jgr.2015.02.003",
        "matrix": "80% 甲醇（非纯水），仅作温度依赖参照",
    },
    "pyrolysis_diterpene_alkaloid": {
        "title": "Variations in the Aconitine Content of Aconiti Lateralis Radix Praeparata by Stir-Frying with Sand",
        "journal": "Evid Based Complement Alternat Med",
        "year": 2021,
        "doi": "10.1155/2021/7243052",
        "matrix": "干热砂炒（无水，路径是脱水/异构化，不是水解）",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    if not CAL.exists():
        print("找不到 %s，先跑 tools/fit_extent_kinetics.py" % CAL.relative_to(ROOT))
        return 2
    cal = json.loads(CAL.read_text(encoding="utf-8"))
    kin = json.loads(KIN.read_text(encoding="utf-8"))

    entries = []
    for rxn, info in (cal.get("by_reaction") or {}).items():
        if not info.get("q10_mean"):
            continue
        entries.append({
            "reaction": rxn,
            "temperatures_C": info.get("temperatures_C"),
            "q10_measured": round(float(info["q10_mean"]), 3),
            "ea_kJ_per_mol": (round(float(info["arrhenius"]["ea_kJ_per_mol"]), 1)
                              if info.get("arrhenius") else None),
            "source": SOURCES.get(rxn, {}),
        })

    q10 = kin.setdefault("q10", {})
    vals = [e["q10_measured"] for e in entries]
    water_vals = [e["q10_measured"] for e in entries
                  if "甲醇" not in e["source"].get("matrix", "")
                  and "干热" not in e["source"].get("matrix", "")]

    q10["train_calibration"] = {
        "status": "partially_supported",
        "measured": entries,
        "q10_range_measured": [round(min(vals), 3), round(max(vals), 3)] if vals else None,
        "water_only_range": [round(min(water_vals), 3), round(max(water_vals), 3)]
        if water_vals else None,
        "decision": (
            "保留 value = 2.0。实测两条独立数据给出 1.86（80% 甲醇、纯标准品）与 2.60"
            "（水/蒸汽、药材基质），当前默认值落在实测区间内部；干热砂炒那条（Q10=4.26）"
            "是脱水/异构化路径，不能用于水解反应。只有当同一反应出现 >=3 组独立实测、"
            "且中位数偏离 2.0 超过 +-0.3 时才改默认值。"
        ),
        "calib_report": "reports/kinetics_calibration_20261106.json",
        "measurements": "conditions/kinetics_measurements.json",
        "note": "本块只记录实测与判断，不参与任何计算；计算仍走 q10.value。",
    }

    if args.dry:
        print(json.dumps(q10["train_calibration"], ensure_ascii=False, indent=2))
        return 0

    KIN.write_text(json.dumps(kin, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("已写入 %s" % KIN.relative_to(ROOT))
    for e in entries:
        print("  %-34s T=%-12s Q10=%.2f  Ea=%s  %s"
              % (e["reaction"], e["temperatures_C"], e["q10_measured"],
                 e["ea_kJ_per_mol"], e["source"].get("doi")))
    print("q10.value 未改：%s" % q10.get("value"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
