# -*- coding: utf-8 -*-
r"""修醌还原的产物（应芳香化），并查清校验器为什么放行了这个不平衡的规则。

【问题】
    SMARTS:  [O:1]=[C:2][C:3]=[O:4]>>[OH:1][C:2][C:3][OH:4]
    co_reagents = {"H2": 2}

    邻苯醌 C6H4O2（C2/C3 是 sp2 碳，不带氢）
      + 2 H2  →  左边 C6H6O2
    产物：碳氧双键变单键后，C2/C3 各补 1 个氢 → C6H8O2
      → 右边 C6H8O2

    ★ 左右差 2 个氢，应该判 UNBALANCED ★
    但校验器报的是 PASS。

【正确答案】
    邻苯醌还原成【邻苯二酚】（芳香）：
      C6H4O2 + H2 → C6H6O2（Oc1ccccc1O）
    产物 SMARTS 里 C2/C3 应写成芳香碳 [c:2]/[c:3]，RDKit 会自动芳香化。

【本脚本要回答】
    为什么校验器放行了？是盲点，还是我算错了？
"""
import json
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdMolDescriptors

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}
r = by_id["reduction_quinone_001"]

print("=" * 94)
print("① 先看校验器自己的账本")
print("=" * 94)

import sys
sys.path.insert(0, str(STAGE / "rules"))
sys.path.insert(0, str(STAGE / "libs"))
from schema import load_rules, empirical_balance, _load_substrates

profiles, rules = load_rules(str(F))
subs = _load_substrates(r"D:\TCMAI\tcm.db", 2500)
bal = empirical_balance(r, subs, engine="rdchiral")
print(f"  匹配底物 {bal['matched_substrates']} | 配平 {bal['balanced']} | "
      f"不平衡 {bal['unbalanced']}")
print(f"  漏写片段 {bal['atom_loss']} | 凭空造原子 {bal['atom_creation']}")

# 手工算一个具体底物
print()
print("=" * 94)
print("② 手工核算：邻苯醌这个底物")
print("=" * 94)
SUB = "O=C1C=CC=CC1=O"
m = Chem.MolFromSmiles(SUB)

from rdkit.Chem.rdMolDescriptors import CalcMolFormula


def counts(mol):
    """和校验器一致的元素计数。"""
    d = {}
    mol = Chem.AddHs(mol)
    for a in mol.GetAtoms():
        d[a.GetSymbol()] = d.get(a.GetSymbol(), 0) + 1
    return d


co = r.get("co_reagents") or {}
by = r.get("byproducts") or {}
print(f"  底物 {SUB}  {counts(m)}")
print(f"  co_reagents = {co}   byproducts = {by}")

# rdkit 产物
rxn = AllChem.ReactionFromSmarts(r["smarts"])
for ps in rxn.RunReactants((m,))[:1]:
    total = {}
    for p in ps:
        pc = Chem.Mol(p)
        Chem.SanitizeMol(pc)
        print(f"  产物 {Chem.MolToSmiles(pc)}  {CalcMolFormula(pc)}  {counts(pc)}")
        for k, v in counts(pc).items():
            total[k] = total.get(k, 0) + v
    print(f"  产物合计 {total}")
    print(f"  ★ 校验器怎么算 co/by 的？看 empirical_balance 的实现")

print()
print("=" * 94)
print("③ 判定")
print("=" * 94)
print("""
  如果校验器对 co_reagents 的处理与这里不同（比如没把 H2 当原子加进去、
  或者产物的隐式氢没算），那就是**校验器盲点**。

  如果算出来左右确实相等，那是我手工核算错了。

  无论哪种，规则本身的问题（产物该芳香化）都已确认：
    邻苯醌 + H2 → 邻苯二酚 C6H6O2，而引擎给出 C6H8O2。
""")
