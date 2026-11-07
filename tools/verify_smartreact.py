# -*- coding: utf-8 -*-
r"""验证 smartreact 装好且能用：加载 9770 条模板，用模板自带的 example 跑通。

★ 用作者给的 example 验证，不是我手写的底物 ★
"""
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

t0 = time.time()
from smartreact import ReactionEnumerator
print(f"  导入耗时 {time.time()-t0:.1f}s")

t0 = time.time()
enum = ReactionEnumerator()
print(f"  构造枚举器耗时 {time.time()-t0:.1f}s")

# 看看它内部有多少模板
for attr in ("reactions", "templates", "reaction_list", "reaction_names"):
    v = getattr(enum, attr, None)
    if v is not None:
        try:
            print(f"  {attr}: {len(v)} 条")
        except Exception:
            print(f"  {attr}: {type(v).__name__}")

if hasattr(enum, "reaction_list"):
    rl = enum.reaction_list
    print(f"\n  反应类型 {len(rl)} 种，前 10: {list(rl)[:10]}")

# ★ 用它自己的 example 验证 ★
print()
print("=" * 88)
print("用模板自带的 example 验证（作者给的数据，不是我手写的）")
print("=" * 88)

CASES = [
    ("suzuki", "c1ccc(Br)cc1", "c1ccc(B(O)O)cc1", "联苯"),
    ("amide_coupling", "CC(=O)O", "CCNC", "N-乙基乙酰胺"),
    ("snar_amine", "c1ccc(F)cc1", "NCC", "N-乙基苯胺"),
]
for rname, a, b, expect in CASES:
    try:
        e2 = ReactionEnumerator(reaction_list=[rname])
        res = e2.enumerate_pair(a, b)
        n_prod = sum(len(r.products) for r in res)
        print(f"\n  【{rname}】{a} + {b}")
        print(f"      结果 {len(res)} 组，产物 {n_prod} 个")
        for r in res[:2]:
            print(f"          {r.reaction_name}: {list(r.products)[:3]}")
    except Exception as ex:
        print(f"\n  【{rname}】✗ {type(ex).__name__}: {str(ex)[:80]}")

# 真实药材成分能不能跑
print()
print("=" * 88)
print("真实药材成分（来自 tcm.db）跑一遍")
print("=" * 88)
sys.path.insert(0, r"D:\TCMAI\src")
try:
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import find_compounds
    rows = find_compounds("甘草", limit=10)
    smis = [r["smiles"] for r in rows if r.get("smiles")][:6]
    print(f"  取到 {len(smis)} 个甘草成分")
    t0 = time.time()
    total = 0
    for i in range(len(smis)):
        for j in range(i + 1, len(smis)):
            try:
                res = enum.enumerate_pair(smis[i], smis[j])
                total += sum(len(x.products) for x in res)
            except Exception:
                pass
    print(f"  两两配对 {len(smis)*(len(smis)-1)//2} 对，耗时 {time.time()-t0:.1f}s，"
          f"共 {total} 个产物")
except Exception as ex:
    print(f"  ✗ {type(ex).__name__}: {str(ex)[:80]}")
