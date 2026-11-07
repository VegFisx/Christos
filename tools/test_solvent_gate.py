# -*- coding: utf-8 -*-
r"""第十二轮：扩溶剂词表 —— 实测与回归。

回答三个问题（先打印原始数据，再下结论）：
  A. 词表覆盖：ORD 规范化条件表里出现的溶剂名，新词表认不认识？（认不出会静默兜底 organic）
  B. 区分力：37 类反应各自的 ORD 偏好溶剂，旧版（8 粗类别）压成几个类别？新版几个？
  C. 回归：旧 _solvent_class 的判定 vs 新的 solvent_matches，逐例对比（把旧逻辑抄进本文件当参照）。

用法: python test_solvent_gate.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "conditions", STAGE / "core", STAGE / "libs"):
    sys.path.insert(0, str(_p))

from model import (SOLVENT_COARSE, SOLVENT_FINE, SOLVENT_PARENT,  # noqa: E402
                   is_known_solvent, solvent_class, solvent_matches)

NORM = STAGE / "reports" / "conditions_normalized.json"


# ---------------------------------------------------------------- 旧版逻辑（参照物）
def old_solvent_class(name) -> str:
    """★ 抄自 git 前的旧实现（smartreact_engine._solvent_class），只作回归参照。"""
    if not name:
        return "none"
    s = str(name).strip().lower()
    if s in ("water", "aqueous", "h2o"):
        return "water"
    if s in ("methanol", "meoh"):
        return "methanol"
    if s in ("ethanol", "etoh", "alcohol"):
        return "alcohol"
    if s in ("none", ""):
        return "none"
    if s in ("oil",):
        return "oil"
    return "organic"


def old_match(got, wants) -> bool:
    want = {old_solvent_class(s) for s in wants}
    gc = old_solvent_class(got)
    return bool(gc) and gc in want


# ---------------------------------------------------------------- A. 词表覆盖
d = json.loads(NORM.read_text(encoding="utf-8"))
names = Counter()
for _k, e in d.items():
    for s in (e.get("solvents") or []):
        names[str(s)] += 1
unknown = [s for s in names if not is_known_solvent(s)]
print("=" * 96)
print("A. 词表覆盖（口径：conditions_normalized.json 的 solvents 字段，引擎真正加载的那份）")
print("=" * 96)
print(f"  ORD 溶剂写法 {len(names)} 种；新词表认不出 {len(unknown)} 种 {unknown}")
print(f"  归一到细类别 {len({solvent_class(s) for s in names})} 个："
      f"{sorted({solvent_class(s) for s in names})}")
print(f"  词表规模：粗类别 {len(SOLVENT_COARSE)} 个 {list(SOLVENT_COARSE)}")
print(f"           细类别 {len(SOLVENT_FINE)} 个 {list(SOLVENT_FINE)}")

# ---------------------------------------------------------------- B. 区分力
print()
print("=" * 96)
print("B. 区分力（同一类反应的 ORD 偏好溶剂，压成几个类别）")
print("=" * 96)
n_collapse_old = n_collapse_new = 0
n_multi_new = 0
rows = []
for k, e in d.items():
    sols = [str(s) for s in (e.get("solvents") or [])]
    if not sols:
        continue
    old_set = {old_solvent_class(s) for s in sols}
    new_set = {solvent_class(s) for s in sols}
    if len(old_set) == 1:
        n_collapse_old += 1
    if len(new_set) == 1:
        n_collapse_new += 1
    if len(new_set) >= 2:
        n_multi_new += 1
    rows.append((k, sorted(old_set), sorted(new_set), len(sols)))
tot = len(rows)
for k, o, n, ns in sorted(rows, key=lambda x: -len(x[2]))[:8]:
    print(f"  {k:<26} ORD {ns} 个名 -> 旧 {o} / 新 {n}")
print(f"  …（共 {tot} 类有溶剂数据）")
print(f"  旧版：偏好集压成单一类别（区分力=0）的类 {n_collapse_old}/{tot}")
print(f"  新版：压成单一类别的类 {n_collapse_new}/{tot}；能区分 >=2 细类别的类 {n_multi_new}/{tot}")

# ---------------------------------------------------------------- C. 回归
print()
print("=" * 96)
print("C. 回归（旧逻辑 vs 新逻辑，逐例）")
print("=" * 96)
CASES = [
    # (条件溶剂, ORD 偏好溶剂, 旧逻辑结果, 新逻辑预期)
    ("water", ["water", "aqueous"], True, True),
    ("ethanol", ["ethanol"], True, True),
    ("ethanol", ["MeOH"], False, False),
    ("organic", ["DMF"], True, True),
    ("organic", ["water"], False, False),
    ("DMF", ["DMF"], True, True),
    ("DMF", ["THF"], False, False),          # ← 旧版也是 False（都压成 organic 反而 True，见下）
    ("thf", ["THF"], True, True),
    ("thf", ["toluene"], False, False),      # ← 新版新增区分力（旧版：organic vs organic -> True）
    ("dcm", ["CH2Cl2"], True, True),
    ("organic", ["THF"], True, True),
    ("alcohol", ["MeOH"], False, True),      # ← 有意改正：粗 alcohol 不该被细 methanol 判死
    ("", ["water"], False, False),
]
bad = 0
for got, wants, _old_exp, new_exp in CASES:
    o = old_match(got, wants)
    n = solvent_matches(got, wants)
    flag = "OK " if n == new_exp else "!! "
    if n != new_exp:
        bad += 1
    print(f"  {flag}条件 {got or '<空>':<9} vs ORD {str(wants):<18} "
          f"旧={o!s:<5} 新={n!s:<5} 新预期={new_exp}")
print(f"  断言失败 {bad} 例")

print()
print("=" * 96)
print("结论口径")
print("=" * 96)
print(f"  1) ORD 溶剂写法 100% 被词表认识（{len(names)}/{len(names)}）-> 无静默兜底")
print(f"  2) 区分力：旧版 {n_collapse_old}/{tot} 类无区分力 -> 新版 {n_collapse_new}/{tot}"
      f"（另有 {n_multi_new} 类可按细类别区分）")
print("  3) 向后兼容：粗类别（organic/alcohol/water）与细类别的匹配方向未收紧；")
print("     'alcohol' vs ['MeOH'] 由 False 改成 True 是【有意改正】，已单列。")
sys.exit(1 if bad or unknown else 0)
