# -*- coding: utf-8 -*-
r"""跑一遍**离线回归套件**，给出一张 PASS/FAIL 表（第七十五轮；梯子不通时也能跑）。

用法：
    python tools\run_regression_suite.py            # 默认套件
    python tools\run_regression_suite.py --fast     # 只跑秒级的
    python tools\run_regression_suite.py --only test_frontend.py,test_e2e.py

纪律：每个脚本的**退出码与最后几行**都原样打印，失败**不静默**。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
PY = sys.executable

SUITE = [
    ("audit_mapped_safety.py", "原子映射安全（提交前必跑）", False),
    ("test_reaction_cases.py", "反应级验收 66 条", False),
    ("db_cases.py", "真实底物用例 5 条", False),
    ("verify_case_conversion.py", "用例 DB 化无偷换", False),
    ("check_herb_naming.py", "药材名口径（HERB 本名/别名）", False),
    ("test_frontend.py", "前端/桥接", False),
    ("test_e2e.py", "端到端", True),
    ("test_condition_gate.py", "条件层门控", True),
    ("test_solvent_gate.py", "溶剂门", True),
    ("test_required_reagent_gate.py", "必需试剂门", True),
    ("test_bireactant.py", "双反应物", True),
    ("check_deriver_regression.py", "deriver 回归", True),
    ("check_quinone_regression.py", "对醌回归", True),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="只跑秒级脚本")
    ap.add_argument("--only", default="", help="逗号分隔的脚本名")
    a = ap.parse_args()
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    rows, bad = [], 0
    for name, desc, slow in SUITE:
        if only and name not in only:
            continue
        if a.fast and slow:
            continue
        p = STAGE / "tools" / name
        if not p.exists():
            print("  %-34s ★ 脚本不存在" % name)
            bad += 1
            continue
        t0 = time.time()
        r = subprocess.run([PY, str(p)], cwd=str(STAGE), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=3600)
        dt = time.time() - t0
        tail = [ln for ln in (r.stdout or "").strip().splitlines()[-3:]]
        ok = (r.returncode == 0)
        bad += 0 if ok else 1
        rows.append((name, desc, ok, dt, tail, (r.stderr or "").strip().splitlines()[-2:]))
        print("  %-34s %-22s %s  %.1fs" % (name, desc, "PASS" if ok else "FAIL", dt))
        for ln in tail:
            print("        %s" % ln[:130])
        if not ok:
            for ln in (r.stderr or "").strip().splitlines()[-4:]:
                print("      ! %s" % ln[:130])
    print()
    print("  套件结果：%d 个脚本，%d 失败" % (len(rows), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
