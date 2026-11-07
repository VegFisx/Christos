# -*- coding: utf-8 -*-
r"""校验可用率判据本身：拿【已知化学合法的拆解】和【已知退化的路线】各测几条。

如果合法路线被误杀 -> 判据错了；
如果合法通过、退化被拒 -> 判据可用，那 0% 可用率就是搜索的真问题。

用法: python check_usability_criteria.py
"""
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
import importlib  # noqa: E402
import eval_route_usability as _e  # noqa: E402
importlib.reload(_e)
from eval_route_usability import judge_step  # noqa: E402
from retro_search import Step  # noqa: E402

# (说明, 目标, [前体...], 期望)
CASES = [
    # ---- 已知化学合法（真拆解，分子明显变小）----
    ("酰胺偶联：沙洛酚", "O=C(NCCc1ccc(O)cc1)c1ccccc1O",
     ["NCCc1ccc(O)cc1", "O=C(O)c1ccccc1O"], "合法"),
    ("乙酰化：阿司匹林", "CC(=O)Oc1ccccc1C(=O)O",
     ["O=C(O)c1ccccc1O", "CC(=O)OC(C)=O"], "合法"),
    ("酯化：阿司匹林(酸+醇路线)", "CC(=O)Oc1ccccc1C(=O)O",
     ["CC(=O)O", "Oc1ccccc1C(=O)O"], "合法"),
    ("Mitsunobu/醚化：苯甲醚", "COc1ccccc1",
     ["Oc1ccccc1", "CO"], "合法"),
    ("还原胺化：苄胺", "NCc1ccccc1",
     ["O=Cc1ccccc1", "N"], "合法"),
    ("Suzuki：联苯", "c1ccc(-c2ccccc2)cc1",
     ["B(O)O.c1ccccc1", "Brc1ccccc1"], "合法"),
    # ---- 已知退化（把目标换个基团再变回来 / 没变小）----
    ("退化：氨基版目标", "COc1cc(CC=C(C)C)cc(OC)c1O",
     ["COc1cc(CC=C(C)C)cc(OC)c1N", "O=S(=O)(O)O"], "退化"),
    ("退化：溴代版目标", "COc1cc(CC=C(C)C)cc(OC)c1O",
     ["COc1cc(CC=C(C)C)cc(OC)c1Br", "CC(=O)O"], "退化"),
    ("退化：甲基化", "COc1ccccc1O",
     ["COc1ccccc1O", "CCl"], "退化"),
    ("退化：前体更大", "Cc1ccc(O)cc1",
     ["Cc1ccc(OC(=O)c2ccccc2)cc1", "O"], "退化"),
]

print("=" * 92)
print("可用率判据自校验")
print("=" * 92)
n_ok = 0
for note, target, pres, expect in CASES:
    st = Step(target=target, precursors=tuple(pres), template="t", reaction_name="x")
    bad = judge_step(st)
    got = "退化" if bad else "合法"
    mark = "OK " if got == expect else "XX "
    if got == expect:
        n_ok += 1
    print(f"  {mark} [{expect}] {note}")
    print(f"        {target[:52]}  <-  {pres}")
    if bad:
        print(f"        触发 {bad}")
print()
print(f"  {n_ok}/{len(CASES)} 符合期望")
print("  合法路线若被误杀 -> 判据过严；否则 0% 可用率是搜索的真问题。")
