# -*- coding: utf-8 -*-
r"""精确验证：没改过 SMARTS 的规则，新旧产物到底差在哪。

假设：两个引擎【枚举产物的顺序不同】，而 max_products_per_molecule 会截断，
      于是"取到的前 N 个"不一样 —— 属于实现差异，不是缺陷。
      若成立：把上限放大到很大，两边的【全集】应当一致。
"""
import sys
from collections import Counter
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
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


rows = []
for h in ("甘草", "附子", "干姜"):
    rows.extend(find_compounds(h, limit=20))
print(f"成分 {len(rows)} 个\n")

RULES = ["羟基氧化", "芳香环羟基化", "酮还原", "烯烃水合"]

print("=" * 96)
print("A. 默认上限下，逐规则比较产物集合")
print("=" * 96)
old = tcm_analyzer.predict_reactions(rows)
new = compat.predict_reactions(rows, legacy_filter=True, threshold=0.0)

for rn in RULES:
    o = {canon(p["smiles"]) for p in old if p["rxn"] == rn}
    n = {canon(p["smiles"]) for p in new if p["rxn"] == rn}
    o.discard(None)
    n.discard(None)
    print(f"  {rn:<16} 旧 {len(o):>3}  新 {len(n):>3}  "
          f"共有 {len(o & n):>3}  旧独有 {len(o - n):>3}  新独有 {len(n - o):>3}")
    for s in list(o - n)[:2]:
        print(f"      旧独有: {s[:70]}")
    for s in list(n - o)[:2]:
        print(f"      新独有: {s[:70]}")

print()
print("=" * 96)
print("B. 把上限放大后，再比一次（检验「截断顺序」假设）")
print("=" * 96)
# 临时把这几条规则的上限调大
import json
F = STAGE / "rules" / "rules.json"
data = json.loads(F.read_text(encoding="utf-8"))
backup = {}
for r in data["rules"]:
    if r["name"] in RULES:
        backup[r["name"]] = r.get("max_products_per_molecule")
        r["max_products_per_molecule"] = 100
F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# 清缓存，让新上限生效
compat._ENGINE = None
new2 = compat.predict_reactions(rows, legacy_filter=True, threshold=0.0)

for rn in RULES:
    o = {canon(p["smiles"]) for p in old if p["rxn"] == rn}
    n = {canon(p["smiles"]) for p in new2 if p["rxn"] == rn}
    o.discard(None)
    n.discard(None)
    print(f"  {rn:<16} 旧 {len(o):>3}  新(上限100) {len(n):>3}  "
          f"共有 {len(o & n):>3}  旧独有 {len(o - n):>3}  新独有 {len(n - o):>3}")

# 还原
for r in data["rules"]:
    if r["name"] in backup:
        r["max_products_per_molecule"] = backup[r["name"]]
F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
compat._ENGINE = None
print("\n（上限已还原）")

print()
print("=" * 96)
print("判定")
print("=" * 96)
print("""
  若 B 里「旧独有」大幅减少 → 说明差异主要来自【截断取前 N 个的顺序】，
  属于两个反应引擎的实现差异，不是规则或引擎的缺陷。
  若 B 里仍有大量「旧独有」→ 需要继续查。
""")
