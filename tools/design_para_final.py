# -*- coding: utf-8 -*-
r"""修 SMARTS 的键类型问题：默认键是「单键或芳香键」，跨双键的路径匹配不上。

★ 根因

  对苯醌的环是 C1-C2=C3-C4（单-双-单 交替）。
  SMARTS 里不写键符号时，默认是【单键或芳香键】：
      [C:2][#6:5][#6:6][C:3]
            ^^^^^^  要求 C5-C6 之间是单键，但实际是双键 → 匹配失败
  所以对苯醌一条都匹配不上，而 1,4-萘醌恰好路径上都是单键，就匹配上了。

  修法：把中间的键写成 ~（任意键）。

★★ 这是个值得记住的 SMARTS 陷阱 ★★
  以前也踩过类似的：[CX4H:3] 把氢数写死、[C:] 只认脂肪碳。
  这次是【键类型】写死。
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ---------------- 对醌还原 ----------------
RED_OLD = "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]"
RED_NEW = "[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2]~[c:5]~[c:6]~[c:3][OH:4]"

# ---------------- 对二酚氧化 ----------------
# 氧化方向的反应物侧本来就是芳香环，键是芳香键，默认能匹配；
# 但产物侧的 C-C 键类型也要写对
OX_OLD = "[OH:1][c:2][c:5][c:6][c:3][OH:4]>>[O:1]=[C:2][c:5][c:6][C:3]=[O:4]"

RED_SUBS = [
    ("对苯醌", "O=C1C=CC(=O)C=C1", "C6H4O2", "对苯二酚 C6H6O2"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "C10H6O2", "1,4-萘二酚 C10H8O2"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "C14H8O2", "蒽氢醌 C14H10O2"),
    ("大黄素", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O", "C15H10O6", "相应二酚"),
    ("邻苯醌（不该管）", "O=C1C=CC=CC1=O", "C6H4O2", "—"),
    ("辅酶Q0型（甲基对醌）", "CC1=CC(=O)C(C)=CC1=O", "C8H8O2", "相应二酚"),
]

OX_SUBS = [
    ("对苯二酚", "Oc1ccc(O)cc1", "C6H6O2", "对苯醌 C6H4O2"),
    ("1,4-二羟基萘", "Oc1ccc(O)c2ccccc12", "C10H8O2", "1,4-萘醌 C10H6O2"),
    ("蒽氢醌", "Oc1c2ccccc2c(O)c2ccccc12", "C14H10O2", "9,10-蒽醌 C14H8O2"),
    ("邻苯二酚（不该管）", "Oc1ccccc1O", "C6H6O2", "—"),
]


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败: {str(e)[:40]}"
    m = Chem.MolFromSmiles(sub)
    patt = rxn.GetReactantTemplate(0)
    nm = len(m.GetSubstructMatches(patt))
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"模板{nm} 运行异常 {str(e)[:32]}"
    if not res:
        return f"模板{nm} 无产物"
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
    return f"模板{nm} → " + " ؛ ".join(out)


print("=" * 100)
print("① 对醌还原")
print("=" * 100)
for label, sm in (("旧（默认键，跨双键失败）", RED_OLD), ("新（~ 任意键）", RED_NEW)):
    print(f"\n【{label}】{sm}")
    for name, sub, ein, eout in RED_SUBS:
        print(f"    {name:<22} 期望 {ein}→{eout}")
        print(f"        {run(sm, sub)}")

print()
print("=" * 100)
print("② 对二酚氧化")
print("=" * 100)
print(f"\n【{OX_OLD}】")
for name, sub, ein, eout in OX_SUBS:
    print(f"    {name:<22} 期望 {ein}→{eout}")
    print(f"        {run(OX_OLD, sub)}")

print()
print("=" * 100)
print("③ 顺带验证：现有邻位规则有没有同样的键类型问题")
print("=" * 100)
ORTHO_OX = "[OH:1][c:2][c:3][OH:4]>>[O:1]=[C:2][C:3]=[O:4]"
ORTHO_RED = "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]"
for name, sub in (("邻苯二酚", "Oc1ccccc1O"), ("邻苯醌", "O=C1C=CC=CC1=O")):
    print(f"  {name:<12} 氧化 {run(ORTHO_OX, sub)}")
for name, sub in (("邻苯醌", "O=C1C=CC=CC1=O"),):
    print(f"  {name:<12} 还原 {run(ORTHO_RED, sub)}")
