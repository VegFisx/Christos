# -*- coding: utf-8 -*-
r"""确认旧引擎（你项目里的 tcm_analyzer）能在只读模式下跑起来。

要拿到：
  · predict_reactions 的真实产物
  · 返回结构
  · 耗时
这样下一轮才能做新旧正面比对。
"""
import sys
import time
from pathlib import Path

TCMAI_SRC = Path(r"D:\TCMAI\src")
sys.path.insert(0, str(TCMAI_SRC))

print("=" * 88)
print("尝试导入旧引擎")
print("=" * 88)
try:
    import tcm_analyzer
    print("  ✓ import tcm_analyzer 成功")
except Exception as e:
    import traceback
    print(f"  ✗ 失败: {type(e).__name__}: {e}")
    traceback.print_exc()
    raise SystemExit(1)

print(f"  规则数 REACTIONS = {len(tcm_analyzer.REACTIONS)}")
print(f"  RULE_LIMITS = {getattr(tcm_analyzer, 'RULE_LIMITS', '(无)')}")

print()
print("=" * 88)
print("用几个已知分子试跑 predict_reactions")
print("=" * 88)
comps = [
    {"smiles": "COC(=O)c1ccccc1", "name": "苯甲酸甲酯", "herb_name": "测试"},
    {"smiles": "Oc1ccc(O)cc1", "name": "对苯二酚", "herb_name": "测试"},
    {"smiles": "OC[C@H]1O[C@@H](Oc2ccccc2CO)[C@H](O)[C@@H](O)[C@@H]1O",
     "name": "水杨苷", "herb_name": "测试"},
    {"smiles": "CC(=O)Oc1ccccc1", "name": "乙酸苯酯", "herb_name": "测试"},
]
t0 = time.time()
try:
    ps = tcm_analyzer.predict_reactions(comps)
    dt = time.time() - t0
    print(f"  ✓ 产出 {len(ps)} 个产物，耗时 {dt*1000:.0f} ms")
    print(f"  返回结构（第一个）: {list(ps[0].keys()) if ps else '(空)'}")
    for p in ps[:10]:
        print(f"    {p['formula']:<12}{p['rxn']:<16}{p['smiles'][:44]}")
    print(f"  _LAST_RXN_STATS: {len(tcm_analyzer._LAST_RXN_STATS)} 条规则有产出")
    nz = {k: v for k, v in tcm_analyzer._LAST_RXN_STATS.items() if v}
    print(f"  有产出的规则: {nz}")
except Exception as e:
    import traceback
    print(f"  ✗ 失败: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 88)
print("读取真实药材成分（复用你项目的 db_utils）")
print("=" * 88)
try:
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import find_compounds
    rows = find_compounds("甘草", limit=20)
    print(f"  ✓ 甘草 {len(rows)} 个成分")
    if rows:
        print(f"  结构: {list(rows[0].keys())}")
        for r in rows[:5]:
            print(f"    {str(r.get('name'))[:34]:<36}{str(r.get('smiles'))[:44]}")
    print()
    t0 = time.time()
    ps2 = tcm_analyzer.predict_reactions(rows)
    dt = time.time() - t0
    print(f"  → 旧引擎对甘草 20 成分产出 {len(ps2)} 个产物，耗时 {dt:.1f}s")
    from collections import Counter
    c = Counter(p["rxn"] for p in ps2)
    for k, v in c.most_common(10):
        print(f"      {k:<22}{v:>6}")
except Exception as e:
    import traceback
    print(f"  ✗ 失败: {type(e).__name__}: {e}")
    traceback.print_exc()
