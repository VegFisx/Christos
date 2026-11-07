# -*- coding: utf-8 -*-
r"""验证多样性排序：Top-20 是不是真的更多样了？

对比：
  A 纯按分数排（现状）
  B 多样性排序（penalty=0.12）
指标：
  · Top-20 里出现了多少种反应类型
  · 单一规则最多占几行
  · 有没有丢掉真正的高分产物
"""
import sys
from collections import Counter
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from predict import predict

r = predict(herbs=["甘草"], max_per_herb=25, frontier_limit=40,
            max_rounds=8, min_new=10)

main = r.main_products()
print(f"主体产物 {len(main)} 个\n")

print("=" * 92)
print("A) 纯按分数排 Top-20")
print("=" * 92)
topA = main[:20]
cA = Counter(p.rule_name for p in topA)
print(f"  规则种类: {len(cA)}    单一规则最多: {cA.most_common(1)[0][1]} 行"
      f"（{cA.most_common(1)[0][0]}）")
for p in topA[:10]:
    print(f"    {p.score:.3f}  {p.formula:<13}{p.rule_name:<18}{p.source_name[:20]}")

print()
print("=" * 92)
print("B) 多样性排序 Top-20")
print("=" * 92)
for pen in (0.08, 0.12, 0.20):
    topB = r.diverse_ranking(top=20, penalty=pen)
    cB = Counter(p.rule_name for p in topB)
    print(f"  penalty={pen:<5} 规则种类 {len(cB):>2}   "
          f"单一规则最多 {cB.most_common(1)[0][1]} 行（{cB.most_common(1)[0][0]}）")

topB = r.diverse_ranking(top=20, penalty=0.12)
cB = Counter(p.rule_name for p in topB)
print()
print(f"  penalty=0.12 的 Top-10：")
for p in topB[:10]:
    print(f"    {p.score:.3f}  {p.formula:<13}{p.rule_name:<18}{p.source_name[:20]}")

print()
print("=" * 92)
print("★ 关键检查：多样性排序会不会丢掉真正的高分产物？")
print("=" * 92)
hi = [p for p in main if p.score >= 0.75]
hiA = sum(1 for p in topA if p.score >= 0.75)
hiB = sum(1 for p in topB if p.score >= 0.75)
print(f"  全库 >=0.75 的高分产物: {len(hi)} 个")
print(f"  纯分数排 Top-20 里含: {hiA} 个")
print(f"  多样性排 Top-20 里含: {hiB} 个")
print(f"  最高分产物的分数: 纯分数 {topA[0].score:.3f} / 多样性 {topB[0].score:.3f}")

print()
print("  多样性版 Top-20 覆盖到的规则：")
for k, v in cB.most_common():
    print(f"    {v:>3} 行  {k}")

print()
print("=" * 92)
print("结论")
print("=" * 92)
print(f"""
  纯按分数：{len(cA)} 种规则，最多 {cA.most_common(1)[0][1]} 行同一种
  多样性：  {len(cB)} 种规则，最多 {cB.most_common(1)[0][1]} 行同一种

  最高分产物有没有被挤掉：{'没有' if topA[0].smiles == topB[0].smiles else '被换了'}
  高分产物（>=0.75）保留数：{hiA} -> {hiB}
""")
