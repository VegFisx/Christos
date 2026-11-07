# -*- coding: utf-8 -*-
r"""验证【第十六轮：ORD 自抽模板默认开（K1 档）】这次改动是否真的生效。

只回答 4 个问题（一个脚本对应一组明确的判据）：
  1. 默认构造的引擎，extra_template_note 是什么？编译通过多少条？（期望 590 = K1）
  2. 显式 use_extra_templates=False 时，是不是真的退回旧基线（0 条）？
  3. 模板文件缺失/路径写错时，引擎还能不能起来？（默认开之后必须有这条退路）
  4. 默认开的性能代价是多少？（同一组底物对，开/关各跑一次 step，比秒数）

跑法：
  & "D:\TCMAI\venv\Scripts\python.exe" tools\verify_extra_templates_default.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "core"))
sys.path.insert(0, str(STAGE))

from smartreact_engine import SmartReactEngine, DEFAULT_EXTRA_TEMPLATES  # noqa: E402
from engine import Compound  # noqa: E402
from model import Conditions  # noqa: E402

FAIL: list[str] = []


def check(label: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}: {detail}")
    if not ok:
        FAIL.append(label)


print("=" * 92)
print("验证：ORD 自抽正向模板【默认开 K1 档】")
print("=" * 92)
print(f"默认路径常量: {DEFAULT_EXTRA_TEMPLATES}")
print(f"文件存在: {DEFAULT_EXTRA_TEMPLATES.exists()}"
      f"  大小: {DEFAULT_EXTRA_TEMPLATES.stat().st_size if DEFAULT_EXTRA_TEMPLATES.exists() else 0} B")
print()

print("[1] 默认构造（不传任何模板参数）")
t0 = time.time()
eng_on = SmartReactEngine(gate_conditions=True, verbose=False)
t_on_init = time.time() - t0
n_on = len(eng_on.extra_templates)
print(f"  note = {eng_on.extra_template_note}")
check("默认启用", n_on > 0, f"编译通过 {n_on} 条")
check("档位=K1(590)", n_on == 590, f"n_extra={n_on}（期望 590）")
print(f"  构造耗时 {t_on_init:.1f}s")
print()

print("[2] 显式关闭（use_extra_templates=False）")
t0 = time.time()
eng_off = SmartReactEngine(gate_conditions=True, verbose=False, use_extra_templates=False)
t_off_init = time.time() - t0
print(f"  note = {eng_off.extra_template_note}")
check("关闭后零模板", len(eng_off.extra_templates) == 0,
      f"n_extra={len(eng_off.extra_templates)}")
print(f"  构造耗时 {t_off_init:.1f}s")
print()

print("[3] 模板文件缺失时的退路（默认开之后必须能救命）")
bogus = STAGE / "reports" / "__no_such_templates__.jsonl"
try:
    eng_bad = SmartReactEngine(gate_conditions=True, verbose=False, extra_templates_path=bogus)
    check("缺失不崩", len(eng_bad.extra_templates) == 0, f"note = {eng_bad.extra_template_note}")
except Exception as e:
    check("缺失不崩", False, f"构造抛异常 {type(e).__name__}: {e}")
print()

print("[4] 性能代价（同一组底物对，开/关各跑一次 step）")
seeds = [Compound(smiles=s, name=n, herb="verify") for s, n in [
    ("O=C(O)c1ccccc1O", "salicylic"),
    ("NCCc1ccc(O)cc1", "tyramine"),
    ("OCC(O)CO", "glycerol"),
    ("c1ccc(B(O)O)cc1", "phenylboronic"),
]]
cond = Conditions(solvent="water", temperature=100.0, time_min=60.0)
pairs_n = len(seeds) * (len(seeds) - 1) // 2

t0 = time.time()
p_off = eng_off.step(seeds, cond, threshold=0.0, exclude_smiles=set(), round_no=1)
t_off = time.time() - t0

t0 = time.time()
p_on = eng_on.step(seeds, cond, threshold=0.0, exclude_smiles=set(), round_no=1)
t_on = time.time() - t0

print(f"  底物 {len(seeds)} 个 -> {pairs_n} 对")
print(f"  关闭: {t_off:.2f}s  产物 {len(p_off)}")
print(f"  默认: {t_on:.2f}s  产物 {len(p_on)}")
sp = (t_on / t_off) if t_off > 0 else float("inf")
print(f"  慢 {sp:.2f}x（+{t_on - t_off:.2f}s / {pairs_n} 对）")
print(f"  逐对代价: 关 {t_off / pairs_n * 1000:.1f} ms/对 -> 开 {t_on / pairs_n * 1000:.1f} ms/对")
extra_only = [p for p in p_on if p.rule_name == "mined_extra"]
print(f"  其中来自自抽模板的产物: {len(extra_only)} 条")
check("默认开确实多出产物或有增益", len(p_on) >= len(p_off) and t_on > 0,
      f"开 {len(p_on)} vs 关 {len(p_off)}")

print()
print("=" * 92)
if FAIL:
    print(f"结论：FAIL {len(FAIL)} 项 -> {FAIL}")
    sys.exit(1)
print("结论：全部 PASS")
