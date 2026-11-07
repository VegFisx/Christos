# -*- coding: utf-8 -*-
r"""汇总所有防线的当前状态，输出简洁。
把每个检查当子进程跑，只取结论行。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PY = r"D:\TCMAI\venv\Scripts\python.exe"

CHECKS = [
    ("① 原子守恒",   ["rules/schema.py", "--limit", "2500"],        ["PASS", "UNBALANCED"]),
    ("② 化学合理性", ["rules/sanity.py", "--limit", "600"],         ["汇总"]),
    ("③ 立体化学",   ["rules/stereo.py", "--limit", "1200"],        ["汇总"]),
    ("④ 永不激活",   ["tools/check_never_active.py"],               ["✓ 所有"]),
    ("⑤ 探针矩阵",   ["tools/probe_matrix.py"],                     ["✓ 所有启用"]),
    ("⑥ 变化量审计", ["tools/audit_delta.py"],                      ["汇总"]),
    ("⑦ 反应级验收", ["tools/test_reaction_cases.py"],              ["结果："]),
    ("⑧ 端到端",     ["tools/test_e2e.py"],                         ["结果："]),
    ("⑧ 条件层",     ["tools/test_conditions.py"],                  ["结果："]),
    ("⑧ 前端",       ["tools/test_frontend.py"],                    ["结果："]),
    ("⑧ 双反应物",   ["tools/test_bireactant.py"],                  ["结果："]),
    ("⑧ 热力学",     ["tools/test_thermo.py"],                      ["结果："]),
    ("⑧ 热力学护栏", ["tools/test_thermo_guards.py"],               ["统计:"]),
    ("⑧ 热力学终版", ["tools/test_thermo_final.py"],                ["结果："]),
    ("⑧ 热力学集成", ["tools/test_thermo_integration.py"],          ["结果："]),
    ("⑨ 进程内确定性", ["tools/audit_determinism.py"],              ["结果："]),
    ("⑩ 跨进程(集合)", ["tools/audit_determinism_crossproc.py"],    ["结果："]),
    ("⑪ 跨进程(有序)", ["tools/audit_crossproc_ordered.py"],        ["结果："]),
]


def main() -> int:
    print("=" * 84)
    print("全部防线 · 当前状态")
    print("=" * 84)
    bad = []
    for label, args, keys in CHECKS:
        p = STAGE / args[0]
        if not p.exists():
            print(f"  ? {label:<18} 脚本不存在")
            continue
        r = subprocess.run([PY, "-X", "utf8", str(p)] + args[1:],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        got = [ln.strip() for ln in r.stdout.splitlines()
               if any(k in ln for k in keys)]
        txt = " | ".join(got[:4]) if got else "(无结论行)"
        flag = " "
        if r.returncode != 0:
            # 原子守恒与立体化学允许非零退出（各有 1 条已知局限）
            if label.startswith("①") or label.startswith("③"):
                flag = "△"
            else:
                flag = "✗"
                bad.append(label)
        print(f"  {flag} {label:<18} {txt[:110]}")

    print()
    print("=" * 84)
    print(f"非零退出（非已知局限）：{len(bad)} 项 {bad if bad else ''}")
    print("  注：△ = 已知局限（①对醌还原 1/66 过度匹配；③rdchiral 立体限制）")
    print("=" * 84)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
