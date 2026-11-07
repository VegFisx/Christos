# -*- coding: utf-8 -*-
r"""查「脱甲基」规则：差值 H+2 O+1 跟"脱甲基"这个名号对不上。

【疑点】
    脱甲基 = 去掉一个甲基。产物的碳数应当减少（少 1 个碳，或至少少 CH2/CH3）。
    但探针矩阵里它在 6 个底物上的差值都是 H+2 O+1 —— 等于【加了一分子水】。

【要看清的】
    · SMARTS 到底怎么写
    · 对真正的目标底物（苯甲醚）给出什么产物
    · 对甲醇给出什么产物
    · co_reagents / byproducts 声明了什么
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

data = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
by = {r["id"]: r for r in data["rules"]}
r = by["demethylation_aromatic_001"]

print("=" * 96)
print("【脱甲基】完整配置")
print("=" * 96)
for k in ("smarts", "co_reagents", "byproducts", "condition_profile", "priority",
          "max_products_per_molecule", "reversible"):
    print(f"  {k} = {json.dumps(r.get(k), ensure_ascii=False)}")
print()
print(f"  备注：{str(r.get('notes',''))[:300]}")

print()
print("=" * 96)
print("逐个底物看产物")
print("=" * 96)
SUBS = [("苯甲醚（真正的目标）", "COc1ccccc1"),
        ("甲醇", "CO"),
        ("乙酸甲酯", "COC(C)=O"),
        ("苯甲酸甲酯", "COC(=O)c1ccccc1"),
        ("苯甲醛二甲缩醛", "COC(OC)c1ccccc1"),
        ("甲基葡萄糖苷", "CO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O")]

rxn = AllChem.ReactionFromSmarts(r["smarts"])
for name, smi in SUBS:
    m = Chem.MolFromSmiles(smi)
    print(f"\n  【{name}】{smi}")
    print(f"     底物分子式 {CalcMolFormula(m)}")
    for ps in rxn.RunReactants((m,))[:2]:
        fr = []
        tot = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(f"{Chem.MolToSmiles(pc)}({CalcMolFormula(pc)})")
            except Exception:
                fr.append("(非法)")
        print(f"     产物 {' + '.join(fr)}")

print()
print("=" * 96)
print("判定")
print("=" * 96)
print("""
  若产物是「酚 + 某个含碳副产物」→ 规则正确，差值应体现少碳
  若产物是「酚 + 水」之类 → 碳去了哪里？可能被 rdkit 悄悄丢掉了
""")
