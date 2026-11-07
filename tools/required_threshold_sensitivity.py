# -*- coding: utf-8 -*-
r"""第十二/十三轮：必需试剂判据的【阈值敏感性】——0.5 / 20 这两个数是拍的，得看它有多敏感。

口径：对每个 (覆盖率阈值, 最小样本数) 组合，统计
      「有必需件（会参与判零）的反应类型数」与「必需件总数」。
      覆盖率表固定 = reports/aux_reagent_coverage.json。

用法: python required_threshold_sensitivity.py
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
D = json.loads((STAGE / "reports" / "aux_reagent_coverage.json").read_text(encoding="utf-8"))

COVS = (0.35, 0.40, 0.50, 0.60, 0.70)
MINS = (5, 20, 50, 100)

print("=" * 96)
print("必需试剂判据：阈值敏感性（每格 = 有必需件的类数 / 必需件总数）")
print("=" * 96)
hdr = "  覆盖率阈值\\最小样本 " + "".join(f"{m:>10}" for m in MINS)
print(hdr)
for cov in COVS:
    row = f"  {cov:<18}"
    for mn in MINS:
        n_cls = n_units = 0
        for name, e in D.items():
            n = int(e.get("n_reactions", 0))
            if n < mn:
                continue
            req = [r for r in (e.get("required") or []) if r["coverage"] >= cov]
            opt = [r for r in (e.get("optional") or []) if r["coverage"] >= cov]
            # 与引擎同口径：角色归并（这里只数"个体覆盖率过线的分子"，
            # 角色相加的额外收益单独在下一节打印）
            units = len(req) + len(opt)
            if units:
                n_cls += 1
                n_units += units
        row += f"{n_cls:>5}/{n_units:<4}"
    print(row)

print()
print("参考：引擎实际用的是 覆盖率>=0.50 且 样本>=20，并在其之上做【角色归并】")
print("      （同功能分子覆盖率相加，见 core/smartreact_engine.py: REAGENT_ROLE_SMARTS）")
print("      所以引擎实际判零的类数 >= 上表 (0.50, 20) 那一格 —— 由 test_required_reagent_gate.py 打印。")
