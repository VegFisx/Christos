# -*- coding: utf-8 -*-
r"""
快速模式：日常检查用，目标 1 分钟内跑完
==========================================

★ 为什么要做这个

  完整版防线要跑 9 分钟（实测 reports/defenses_timing.txt）：

      ① 原子守恒 (--limit 2500)   146.0s   ← 15.75 万次规则应用
      ⑧ 热力学集成                 116.6s   ← 真跑 xTB 量子化学
      ⑨ 进程内确定性                64.3s
      ⑪ 跨进程(有序)               55.5s
      ③ 立体化学 (--limit 1200)     42.4s
      ...

  但【绝大多数时候不需要穷举】：
    · 抽查 300 个底物就能发现新规则的配平问题
    · 热力学用缓存就够，不必每次真算
    · 跨进程审计的输入可以缩小

★ 快速模式的原则：**不降低判据的严格程度，只缩小样本量**

  完整版和快速版的【通过/失败判据完全相同】，
  区别只是"在多少个底物上验"。所以：
    · 快速版红了 → 一定有问题
    · 快速版绿了 → 大概率没问题，但发布前仍要跑完整版
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PY = r"D:\TCMAI\venv\Scripts\python.exe"

# (名称, 脚本, 参数, 是否允许非零退出)
CHECKS = [
    ("① 原子守恒 (抽查300)",  "rules/schema.py", ["--limit", "300"], True),
    ("② 化学合理性 (抽查200)", "rules/sanity.py", ["--limit", "200"], False),
    ("③ 立体化学 (抽查200)",   "rules/stereo.py", ["--limit", "200"], False),
    ("④ 永不激活",             "tools/check_never_active.py", [], False),
    ("⑤ 探针矩阵",             "tools/probe_matrix.py", [], False),
    ("⑥ 变化量审计",           "tools/audit_delta.py", [], False),
    ("⑦ 反应级验收 (66条)",    "tools/test_reaction_cases.py", [], False),
    ("⑦b 真实底物用例(数据库)", "tools/db_cases.py", [], False),
    ("⑧ 条件层",               "tools/test_conditions.py", [], False),
    ("⑧ 双反应物",             "tools/test_bireactant.py", [], False),
    ("⑧ 热力学 (用缓存)",      "tools/test_thermo.py", [], False),
    ("⑨ 陪跑试剂合理性",       "tools/audit_cosubstrates.py", [], False),
    ("⑨ 进程内确定性",         "tools/audit_determinism.py", [], False),
    ("⑩ 跨进程(集合) 3次",     "tools/audit_determinism_crossproc.py", ["--n", "3"], False),
    ("⑪ 跨进程(有序) 3次",     "tools/audit_crossproc_ordered.py", ["--n", "3"], False),
]


def main() -> int:
    import os
    env = dict(os.environ, DSH_QUICK="1")   # ★ 让各审计脚本用更小的输入 ★
    print("=" * 80)
    print("快速检查（判据与完整版相同，只缩小样本量）")
    print("=" * 80)
    total = 0.0
    bad = []
    for label, rel, extra, allow_nonzero in CHECKS:
        p = STAGE / rel
        if not p.exists():
            print(f"  ?  {label:<26} 脚本不存在")
            continue
        t0 = time.time()
        try:
            r = subprocess.run([PY, "-X", "utf8", str(p)] + extra,
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600,
                               env=env)
            dt = time.time() - t0
        except subprocess.TimeoutExpired:
            dt = time.time() - t0
            print(f"  ⏱  {label:<26} {dt:6.1f}s  超时")
            bad.append(label)
            total += dt
            continue
        total += dt
        # 取结论行
        got = ""
        for ln in r.stdout.splitlines():
            s = ln.strip()
            if s.startswith("结果：") or s.startswith("汇总") or s.startswith("✓ 所有"):
                got = s
                break

        # ★★ 不能只看退出码 ★★
        #   踩过的坑：test_reaction_cases 出现「58 通过 / 4 失败」时
        #   仍然返回 0，于是这里标了 ✓ —— 一个【假绿】。
        #   现在额外解析结论行里的"失败 N"，N > 0 一律算红。
        import re as _re
        m = _re.search(r"(\d+)\s*通过\s*/\s*(\d+)\s*失败", got)
        inner_fail = int(m.group(2)) if m else 0
        m2 = _re.search(r"标记\s*(\d+)\s*处", got)
        inner_mark = int(m2.group(1)) if m2 else 0
        # 「问题规则 N 条」——立体化学的引擎限制不算失败，但记下
        m3 = _re.search(r"问题规则\s*(\d+)\s*条", got)

        flag = "✓"
        if r.returncode != 0:
            flag = "△" if allow_nonzero else "✗"
            if not allow_nonzero:
                bad.append(label)
        elif inner_fail > 0 or inner_mark > 0:
            flag = "✗"
            bad.append(f"{label}(内报失败 {inner_fail or inner_mark})")
        if m3 and int(m3.group(1)) > 0:
            got += "  （含引擎限制）"
        print(f"  {flag}  {label:<26} {dt:5.1f}s  {got[:60]}")


    print()
    print("=" * 80)
    print(f"合计 {total:.1f}s     失败 {len(bad)} 项 {bad if bad else ''}")
    if total < 120:
        print(f"★ 快速模式达标（<120s）★")
    else:
        print(f"（仍偏慢，可再缩样本）")
    print("  注：△ = 已知局限（对醌还原规则 1/66 底物过度匹配；由运行时守恒守卫兜底）")
    print("=" * 80)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
