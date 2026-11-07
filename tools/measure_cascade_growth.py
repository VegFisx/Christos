# -*- coding: utf-8 -*-
r"""量化级联的产物增长规律 —— 回答"是不是迭代多了就爆炸"。

cascade 的机制（读代码得到）：
  每轮：frontier(最多 frontier_limit 个) 两两配对
        -> 产物中"可传播"的进下一轮 frontier（但被 sample 截到 frontier_limit）
  => 每轮配对数 ~ frontier_limit^2 / 2
  => 总产物 ~ 轮数 x frontier_limit^2 x 每对产物数

本实验：固定底物，改 frontier_limit，看单轮产物数怎么变。
若产物数 ~ frontier_limit^2 -> 证实是二次增长（真爆炸）
若 ~ frontier_limit      -> 只是线性（可控）
"""
import sys
import time
from pathlib import Path

_STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules", _STAGE / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound                      # noqa: E402
from cascade import cascade                      # noqa: E402
from model import Conditions                     # noqa: E402
from smartreact_engine import SmartReactEngine    # noqa: E402

SEEDS = [("O=C(O)c1ccccc1O", "水杨酸"),
         ("NCCc1ccc(O)cc1", "酪胺"),
         ("OCC(O)CO", "甘油"),
         ("c1ccc(B(O)O)cc1", "苯硼酸"),
         ("CC(=O)c1ccc(O)cc1", "对羟基苯乙酮")]
seeds = [Compound(smiles=s, name=n, herb="t") for s, n in SEEDS]
cond = Conditions()

print(f"底物 {len(seeds)} 个，max_rounds=3, min_new=1")
print(f"{'frontier_limit':>15} {'轮':>4} {'该轮新产物':>10} {'累计':>8} {'耗时s':>7}")
print("-" * 56)

for fl in (8, 16, 24, 32):
    eng = SmartReactEngine(max_products_per_pair=6, max_pairs=6000)
    t0 = time.time()
    res = cascade(eng, seeds, cond, max_rounds=3, min_new=1, frontier_limit=fl)
    dt = time.time() - t0
    cum = 0
    for st in res.round_stats:
        cum = st.get("cum", cum + st["new"])
        print(f"{fl:>15} {st['round']:>4} {st['new']:>10} {cum:>8} {dt:>7.1f}")
    print(f"{'':>15} 合计 {res.total}")

print()
print("判读：若『该轮新产物』随 frontier_limit 大致呈平方增长 -> 二次爆炸；")
print("      若大致成正比 -> 线性增长。")
