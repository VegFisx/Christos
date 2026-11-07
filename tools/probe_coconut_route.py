# -*- coding: utf-8 -*-
r"""确认 COCONUT 路线是否真的配好了：别名表里的 latin / coconut 配置。"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

ALIAS = Path(r"D:\TCMAI\data\herb_aliases.json")
print(f"别名表: {ALIAS}")
print(f"存在: {ALIAS.exists()}" + (f"  ({ALIAS.stat().st_size/1024:.1f} KB)" if ALIAS.exists() else ""))
print("=" * 88)

if ALIAS.exists():
    d = json.load(open(ALIAS, encoding="utf-8"))
    print(f"配置了 {len(d)} 味药")
    # 统计有多少配了 coconut（拉丁名）
    with_coco = [k for k, v in d.items()
                 if isinstance(v, dict) and v.get("coconut")]
    print(f"★ 其中配了 coconut(拉丁名) 的: {len(with_coco)} 味")
    print()
    for herb in ["甘草", "黄芪", "人参", "附子", "黄连", "大黄", "麻黄"]:
        v = d.get(herb)
        if v is None:
            print(f"   {herb:<6} （别名表里没有）")
        else:
            print(f"   {herb:<6} include={v.get('include')}  coconut={v.get('coconut')}")

# 实测：collect_compounds 走双源 vs 只走 HERB
print()
print("=" * 88)
print("实测：collect_compounds（双源） vs find_compounds（只 HERB）")
print("=" * 88)
from tcm_ro import use_readonly; use_readonly()
from db_utils import collect_compounds, find_compounds  # noqa: E402

for herb in ["甘草", "黄芪"]:
    try:
        herb_only = find_compounds(herb, limit=500)
    except Exception as ex:
        herb_only = []
        print(f"   {herb} find_compounds 失败: {ex}")
    try:
        both, missed = collect_compounds([herb], herb_limit=500,
                                        coconut_limit=2000, return_missed=True)
    except Exception as ex:
        both, missed = [], [f"异常 {ex}"]
    n_coco = sum(1 for c in both if c.get("match_level") == "coconut")
    print(f"   {herb:<6} 只 HERB: {len(herb_only):>4} 个   |   "
          f"双源合计: {len(both):>4} 个（其中 COCONUT {n_coco} 个）  missed={missed}")
