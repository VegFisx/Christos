# -*- coding: utf-8 -*-
r"""逐项测每个检查的耗时，回答"这么久正常吗"。

只测时间，取结论行。跑完输出一张耗时表。
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
PY = r"D:\TCMAI\venv\Scripts\python.exe"

CHECKS = [
    ("① 原子守恒 (2500底物×63规则)", "rules/schema.py", ["--limit", "2500"]),
    ("② 化学合理性 (600底物)",        "rules/sanity.py", ["--limit", "600"]),
    ("③ 立体化学 (1200底物)",         "rules/stereo.py", ["--limit", "1200"]),
    ("④ 永不激活",                    "tools/check_never_active.py", []),
    ("⑤ 探针矩阵 (80探针)",           "tools/probe_matrix.py", []),
    ("⑥ 变化量审计",                  "tools/audit_delta.py", []),
    ("⑦ 反应级验收 (62条)",           "tools/test_reaction_cases.py", []),
    ("⑧ 端到端",                      "tools/test_e2e.py", []),
    ("⑧ 条件层",                      "tools/test_conditions.py", []),
    ("⑧ 前端",                        "tools/test_frontend.py", []),
    ("⑧ 双反应物",                    "tools/test_bireactant.py", []),
    ("⑧ 热力学",                      "tools/test_thermo.py", []),
    ("⑧ 热力学集成",                  "tools/test_thermo_integration.py", []),
    ("⑨ 进程内确定性",                "tools/audit_determinism.py", []),
    ("⑩ 跨进程(集合) 5次子进程",       "tools/audit_determinism_crossproc.py", []),
    ("⑪ 跨进程(有序) 5次子进程",       "tools/audit_crossproc_ordered.py", []),
]

print("=" * 84)
print("逐项耗时")
print("=" * 84)
rows = []
total = 0.0
for label, rel, extra in CHECKS:
    p = STAGE / rel
    if not p.exists():
        print(f"  ?  {label:<32} 脚本不存在")
        continue
    t0 = time.time()
    try:
        r = subprocess.run([PY, "-X", "utf8", str(p)] + extra,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600)
        dt = time.time() - t0
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        print(f"  ⏱  {label:<32} >{dt:6.1f}s  超时")
        rows.append((label, dt))
        total += dt
        continue
    total += dt
    rows.append((label, dt))
    print(f"  {'✓' if r.returncode == 0 else '△'}  {label:<32} {dt:6.1f}s")

print()
print("=" * 84)
print(f"合计 {total:.1f}s（{total/60:.1f} 分钟）")
print("=" * 84)

print()
print("耗时排名（前 8）：")
for label, dt in sorted(rows, key=lambda x: -x[1])[:8]:
    bar = "█" * max(1, int(dt / max(0.1, total) * 50))
    print(f"  {dt:7.1f}s  {dt/total*100:5.1f}%  {bar} {label}")

print()
print("=" * 84)
print("最慢的几项为什么慢")
print("=" * 84)
print("""
  ① 原子守恒：2500 个真实底物 × 63 条规则 ≈ 15.75 万次规则应用，
     每次都要调 rdchiral（约 0.77 毫秒）→ 天然是分钟级。

  ⑧ 热力学系列：真的在跑 xTB 量子化学计算（--ohess 频率计算），
     单个分子几秒到几分钟，这是物理决定的，不是代码慢。

  ⑩⑪ 跨进程审计：脚本本身要跑 5~6 遍（分别在独立进程里），
     所以耗时 ≈ 5~6 × 单次。

  ⑧ 前端：四逆汤类方要跑完整级联（多轮、每轮几千个产物）。
""")
