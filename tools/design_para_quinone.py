# -*- coding: utf-8 -*-
r"""设计「对位醌 / 对位二酚」规则，并逐个变体实测。

现有规则只处理【邻位】（两个官能团的碳直接相连）：
    酚氧化成醌  [OH:1][c:2][c:3][OH:4]      → 邻二酚 → 邻醌
    醌还原     [O:1]=[C:2][C:3]=[O:4]        → 邻醌 → 邻二酚

缺的是【对位】（中间隔 2 个键，两端碳相距 3 键）：
    对苯二酚 → 对苯醌
    1,4-萘二酚 → 1,4-萘醌
    蒽氢醌 → 9,10-蒽醌        ← 论文说明里的「大黄蒽醌」

本脚本试几个 SMARTS 变体，看哪个能同时覆盖苯环/萘环/蒽环体系。
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ---------------- 氧化方向：对二酚 → 对醌 ----------------
OX_VARIANTS = {
    "A 全芳香产物": "[OH:1][c:2][c:5][c:6][c:3][OH:4]>>[O:1]=[C:2][c:5][c:6][C:3]=[O:4]",
    "B 不指定芳香": "[OH:1][c:2][c:5][c:6][c:3][OH:4]>>[O:1]=[C:2][C:5][C:6][C:3]=[O:4]",
    "C 产物含环闭合": "[OH:1][c:2]1[c:5][c:6][c:3]([OH:4])[cH][cH]1>>[O:1]=[C:2]1[C:5][C:6][C:3](=[O:4])C=C1",
}

# ---------------- 还原方向：对醌 → 对二酚 ----------------
RED_VARIANTS = {
    "A 芳香产物": "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "B 不指定芳香": "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][C:2]=[C:5][C:6]=[C:3][OH:4]",
    "C 简单加氢": "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][C:2][C:5][C:6][C:3][OH:4]",
}

OX_SUBS = [
    ("对苯二酚", "Oc1ccc(O)cc1", "C6H6O2", "对苯醌 C6H4O2"),
    ("1,4-二羟基萘", "Oc1ccc(O)c2ccccc12", "C10H8O2", "1,4-萘醌 C10H6O2"),
    ("蒽氢醌", "Oc1c2ccccc2c(O)c2ccccc12", "C14H10O2", "9,10-蒽醌 C14H8O2"),
    ("邻苯二酚（不该被对位规则管）", "Oc1ccccc1O", "C6H6O2", "—"),
]

RED_SUBS = [
    ("对苯醌", "O=C1C=CC(=O)C=C1", "C6H4O2", "对苯二酚 C6H6O2"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "C10H6O2", "1,4-萘二酚 C10H8O2"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "C14H8O2", "蒽氢醌 C14H10O2"),
    ("邻苯醌（不该被对位规则管）", "O=C1C=CC=CC1=O", "C6H4O2", "—"),
]


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败: {str(e)[:44]}"
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return "底物解析失败"
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"异常: {str(e)[:44]}"
    if not res:
        return "(不匹配)"
    out = set()
    for ps in res[:2]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                pc = Chem.RemoveHs(pc)
                fr.append(f"{Chem.MolToSmiles(pc)} [{CalcMolFormula(pc)}]")
            except Exception:
                fr.append("(价态非法)")
        out.add(" + ".join(fr))
    return " ؛ ".join(out)


print("=" * 100)
print("① 氧化方向：对二酚 → 对醌")
print("=" * 100)
for label, sm in OX_VARIANTS.items():
    print(f"\n【{label}】{sm}")
    for name, sub, expect_in, expect_out in OX_SUBS:
        r = run(sm, sub)
        print(f"    {name:<30} 期望 {expect_in}→{expect_out}")
        print(f"        {r}")

print()
print("=" * 100)
print("② 还原方向：对醌 → 对二酚")
print("=" * 100)
for label, sm in RED_VARIANTS.items():
    print(f"\n【{label}】{sm}")
    for name, sub, expect_in, expect_out in RED_SUBS:
        r = run(sm, sub)
        print(f"    {name:<30} 期望 {expect_in}→{expect_out}")
        print(f"        {r}")

print()
print("=" * 100)
print("③ 判定要点")
print("=" * 100)
print("""
  好的变体应当：
    ✓ 对苯醌/对苯二酚 能匹配且分子式正确
    ✓ 1,4-萘醌/萘二酚 能匹配
    ✓ 9,10-蒽醌/蒽氢醌 能匹配        ← 论文说明里承诺的
    ✗ 邻位底物【不该】被这条规则管（那是另一条规则的活）
""")
