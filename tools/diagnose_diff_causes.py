# -*- coding: utf-8 -*-
r"""查：没改过 SMARTS 的规则，为什么新旧产物也会不同？

同口径对比里，这几条规则旧有新无，但它们在新库里【SMARTS 没改过】：
    羟基氧化 26 / 芳香环羟基化 24 / 酮还原 17 / 烯烃水合 11

嫌疑：
  1. 产物数上限不同（旧 RULE_LIMITS vs 新 max_products_per_molecule）
  2. 产物顺序不同 → 先取到的那个不一样
  3. ★运行时守卫把产物丢了★
  4. rdchiral 与 rdkit 产出不同

逐个排查。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
TCMAI_SRC = Path(r"D:\TCMAI\src")
sys.path.insert(0, str(TCMAI_SRC))
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

import tcm_analyzer
import compat

SUSPECT = ["羟基氧化", "芳香环羟基化", "酮还原", "烯烃水合"]

new_rules = {r["name"]: r for r in
             json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]}
old_limits = getattr(tcm_analyzer, "RULE_LIMITS", {})

print("=" * 96)
print("① 产物上限对比")
print("=" * 96)
print(f"  {'规则':<20}{'旧 RULE_LIMITS':>16}{'新 max_products':>18}  {'SMARTS 是否一致'}")
print("  " + "-" * 76)
import csv
from pathlib import Path as _P
paper = {}
with (_P(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")).open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row["SMARTS"].strip()

for n in SUSPECT:
    r = new_rules.get(n)
    if not r:
        continue
    same = "一致" if paper.get(n) == r["smarts"].strip() else "★不同★"
    print(f"  {n:<20}{str(old_limits.get(n)):>16}{str(r.get('max_products_per_molecule')):>18}  {same}")

print()
print("=" * 96)
print("② 拿一个具体底物，分别用两个引擎跑「羟基氧化」")
print("=" * 96)
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds
rows = find_compounds("甘草", limit=60)
# 找一个能被羟基氧化作用的
target = None
patt = Chem.MolFromSmarts("[CH1][OH]")
for rr in rows:
    m = Chem.MolFromSmiles(rr["smiles"]) if rr.get("smiles") else None
    if m is not None and m.HasSubstructMatch(patt):
        target = rr
        break

if target is None:
    print("  没找到合适的底物")
else:
    print(f"  底物: {target['name']}  {target['smiles'][:70]}")

    old = tcm_analyzer.predict_reactions([dict(target)])
    old_h = [p for p in old if p["rxn"] == "羟基氧化"]
    print(f"\n  旧引擎 羟基氧化 → {len(old_h)} 个")
    for p in old_h[:6]:
        print(f"      {p['formula']:<12}{p['smiles'][:56]}")

    for label, kw in (("新引擎 默认", {}),
                      ("新引擎 阈值0", {"threshold": 0.0}),
                      ("新引擎 阈值0+不删小分子", {"threshold": 0.0, "legacy_filter": False})):
        before = getattr(compat, "_ENGINE", None)
        new = compat.predict_reactions([dict(target)], **kw)
        nh = [p for p in new if p["rxn"] == "羟基氧化"]
        print(f"\n  {label} 羟基氧化 → {len(nh)} 个")
        for p in nh[:6]:
            print(f"      {p['formula']:<12}{p['smiles'][:56]}")

    print()
    print("=" * 96)
    print("③ 运行时守卫有没有丢东西")
    print("=" * 96)
    eng = compat._ENGINE
    if eng is None:
        compat._boot()
        eng = compat._ENGINE
    n0 = getattr(eng, "balance_dropped", 0)
    compat.predict_reactions([dict(target)], threshold=0.0)
    n1 = getattr(eng, "balance_dropped", 0)
    print(f"  守卫拦下 {n1 - n0} 组")

    print()
    print("=" * 96)
    print("④ 规则声明的配平参数")
    print("=" * 96)
    for n in SUSPECT:
        r = new_rules.get(n)
        if r:
            print(f"  {n:<20} co={r.get('co_reagents')}  by={r.get('byproducts')}  "
                  f"可逆={r.get('reversible')}")
