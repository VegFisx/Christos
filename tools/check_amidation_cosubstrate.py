# -*- coding: utf-8 -*-
r"""查酰胺化(分子间)的陪跑试剂：氨/甲胺在煎煮里真的存在吗？"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")
from engine import Compound, load_engine
import templates as T

eng, rules, profs = load_engine()
r = next(x for x in rules if x["name"] == "酰胺化(分子间)")
print("SMARTS:", r["smarts"])
print("co_reagents:", r.get("co_reagents"))
print("co_substrate_pool:")
for it in r.get("co_substrate_pool") or []:
    print(f"   smiles={it['smiles']:<16} when_solvent={it.get('when_solvent')}")

# 哪些底物能反应
SUBS = [
    ("苯甲酸", "O=C(O)c1ccccc1"),
    ("乙酸", "CC(=O)O"),
    ("水杨酸", "O=C(O)c1ccccc1O"),
    ("甘草次酸型羧酸", "CC1(C)C2CCC3(C)C(CCC4C3CCC3(C)C(C(=O)O)CCC43)C2C1"),
]
print()
print("=" * 92)
print("各工艺下的酰胺化产物，以及是哪条陪跑试剂起作用")
print("=" * 92)
for cname in ("煎煮", "水提", "醇提", "酸水解", "酶催化"):
    cond = T.get_template(cname)
    cos = eng.available_cosubstrates(r, cond)
    print(f"\n  【{cname}】可用第二反应物: {[c.get('smiles') for c in cos]}")
    for nm, smi in SUBS:
        s = Compound(smiles=smi, name=nm, herb="t")
        ps = eng.apply_rule(r, s, 0.6, 1, cond)
        for p in ps:
            # 从产物反推用了哪条陪跑试剂
            print(f"      {nm:<10} → {p.formula:<14}{p.smiles[:56]}")

print()
print("=" * 92)
print("判定")
print("=" * 92)
print("""
  陪跑试剂的 when_solvent=None 表示【任何工艺下都可用】。
  如果被用的是【氨(N)】或【甲胺(CN)】—— 那就不合理：
    煎煮的水里既没有氨也没有甲胺。
  如果被用的是【甘氨酸(NCC(=O)O)】—— 尚可辩护：
    药材里确实有游离氨基酸。
""")
