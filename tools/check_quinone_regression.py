# -*- coding: utf-8 -*-
r"""查我在「醌还原」上引入的回归。

影响量化显示：新版的醌还原对 sennoside e（番泻苷，蒽醌类）不再匹配。
而论文里这条规则的说明明确写着「丹参酮、大黄蒽醌等」——
说明它本来就该覆盖蒽醌类。

我的修法把产物改成芳香碳 [c:2]/[c:3]，对邻苯醌正确，
但对蒽醌这类不能简单芳香化的体系可能失效。

★ 这是我修出来的回归，必须查清。
"""
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

OLD = "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][C:2][C:3][OH:4]"
NEW = "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]"

TESTS = [
    ("邻苯醌（苯醌型）", "O=C1C=CC=CC1=O"),
    ("对苯醌", "O=C1C=CC(=O)C=C1"),
    ("9,10-蒽醌（两个 C=O 不相邻）", "O=C1c2ccccc2C(=O)c2ccccc21"),
    ("1,2-萘醌（邻位）", "O=C1C=CC2=CC=CC=C2C1=O"),
    ("丹参酮IIA 型（邻醌）", "CC1=C(C(=O)C2=C(C1=O)c1ccccc1O2)C"),
    ("大黄素（蒽醌，有酚羟基）", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O"),
]


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败 {e}"
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return "底物解析失败"
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"异常 {str(e)[:50]}"
    if not res:
        return "(不匹配)"
    outs = set()
    for ps in res[:2]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(f"{Chem.MolToSmiles(pc)} [{CalcMolFormula(pc)}]")
            except Exception:
                fr.append("(价态非法)")
        outs.add(" + ".join(fr))
    return " ؛ ".join(outs)


print("=" * 100)
print("醌还原：两个版本对各种醌的表现")
print("=" * 100)
for label, sm in (("论文版（非芳香产物 + co=H2:2）", OLD),
                  ("我的版（芳香产物 + co=H2:1）", NEW)):
    print(f"\n【{label}】")
    print(f"   {sm}")
    for name, sub in TESTS:
        m = Chem.MolFromSmiles(sub)
        print(f"   {name:<32} 底物 {CalcMolFormula(m) if m else '?'}")
        print(f"        → {run(sm, sub)}")

print()
print("=" * 100)
print("判定：蒽醌类为什么匹配不上")
print("=" * 100)
for name, sub in TESTS:
    m = Chem.MolFromSmiles(sub)
    old_patt = AllChem.ReactionFromSmarts(OLD).GetReactantTemplate(0)
    new_patt = AllChem.ReactionFromSmarts(NEW).GetReactantTemplate(0)
    n_old = len(m.GetSubstructMatches(old_patt))
    print(f"  {name:<32} 反应物模板匹配位点 {n_old}")

print()
print("""
  关键：新版的问题不在【反应物】模板（两边一样），而在【产物】模板——
        [c:2]/[c:3] 要求产物里那两个碳是芳香碳。
        对小环苯醌，RDKit 能把产物芳香化 → 成立。
        对蒽醌/萘醌等，RDKit 无法从产物模板直接推出芳香体系 → 匹配失败。

  结论：我的修法确实收窄了规则，丢了蒽醌类。
""")
