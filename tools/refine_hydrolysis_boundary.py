# -*- coding: utf-8 -*-
r"""把边界定准：水解类里哪几条真的是「气相 ΔG 不可靠」？

疑点：环氧化物开环成二醇 被归在 hydrolysis 类，
      但它是【加成开环】（1 个分子 + 水 → 1 个分子），
      不是【水切断键】（1 个分子 + 水 → 2 个分子）。
      气相 ΔG 对前者可能是准的。

判据区分：
  水【切断】一根键 → 反应前后【片段数不变】（2 → 2）→ 溶剂化驱动，气相算不出
  水【加成】上去   → 片段数减少（2 → 1）→ 有键能驱动，气相算得出
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "core"))

from thermo import Thermo

th = Thermo(n_conf=2)
print(f"Thermo 可用: {th.available}\n")

CASES = [
    # (标签, 类别, 左侧, 右侧, 预期符号, 片段数变化)
    ("酯水解",        "hydrolysis", ["CC(=O)OCC", "O"], ["CC(=O)O", "CCO"], -1, "2→2"),
    ("糖苷水解",      "hydrolysis", ["COC1OC(CO)C(O)C(O)C1O", "O"],
                                    ["OC1OC(CO)C(O)C(O)C1O", "CO"], -1, "2→2"),
    ("酰胺水解",      "hydrolysis", ["CC(=O)N", "O"], ["CC(=O)O", "N"], -1, "2→2"),
    ("亚胺水解",      "hydrolysis", ["CC=N", "O"], ["CC=O", "N"], -1, "2→2"),
    ("★环氧化物开环", "hydrolysis", ["C1CO1", "O"], ["OCCO"], -1, "2→1"),
    ("★内酰胺开环",   "hydrolysis", ["O=C1CCCN1", "O"], ["NCCCC(=O)O"], -1, "2→1"),
    ("水合·烯烃",     "hydration",  ["C=C", "O"], ["CCO"], -1, "2→1"),
    ("水合·烯酮",     "hydration",  ["CC(C)=O", "O"], ["CC(C)(O)O"], -1, "2→1"),
]

print(f"{'案例':<18}{'类别':<12}{'片段':<7}{'ΔG':>9}{'预期':>6}{'判定':>6}")
print("-" * 62)
by_cat = {}
for label, cat, left, right, expect, frags in CASES:
    dg = th.reaction_dg(left, right)
    if dg is None:
        print(f"{label:<18}{cat:<12}{frags:<7}{'失败':>9}{'':>6}{'—':>6}")
        continue
    ok = (dg < 0) if expect < 0 else (dg > 0)
    by_cat.setdefault(cat, []).append((label, dg, ok, frags))
    print(f"{label:<18}{cat:<12}{frags:<7}{dg:>9.1f}"
          f"{'负' if expect < 0 else '正':>6}{'✓' if ok else '✗错':>6}")

print()
print("=" * 62)
print("判定")
print("=" * 62)
for cat, items in by_cat.items():
    bad = [x for x in items if not x[2]]
    print(f"  {cat:<12} {len(items)} 个样本，错 {len(bad)} 个")
    for label, dg, ok, frags in items:
        print(f"      {label:<18}{dg:>8.1f}  {frags}  {'✓' if ok else '✗'}")

print()
print("  按【片段数变化】分组：")
same = [x for xs in by_cat.values() for x in xs if x[3] == "2→2"]
less = [x for xs in by_cat.values() for x in xs if x[3] == "2→1"]
print(f"     2→2（水切断键）: {len(same)} 个，错 {sum(1 for x in same if not x[2])} 个")
print(f"     2→1（水加成型）: {len(less)} 个，错 {sum(1 for x in less if not x[2])} 个")
