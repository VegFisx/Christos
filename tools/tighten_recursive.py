# -*- coding: utf-8 -*-
r"""最后一试：用递归 SMARTS 排除酸酐的过度匹配。

思路：真醌的桥碳（C=O 之间的两个碳）【不应连氧】。
      酸酐的路径会经过连氧的碳 → 被排除。

若这招也不成，就把该规则标为 verify（如实记录局限），不硬凑。
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

SHOULD = [
    ("对苯醌", "O=C1C=CC(=O)C=C1", "C6H6O2"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "C10H8O2"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "C14H10O2"),
    ("大黄素", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O", "C15H12O6"),
    ("辅酶Q0型", "CC1=CC(=O)C(C)=CC1=O", "C8H10O2"),
]
SHOULD_NOT = [
    ("邻苯醌", "O=C1C=CC=CC1=O"),
    ("四氢邻苯二甲酸酐", "O=C1OC(=O)C2CCCC12"),
    ("邻苯二甲酸酐（芳香酸酐）", "O=C1OC(=O)c2ccccc21"),
    ("乙酸酐", "CC(=O)OC(C)=O"),
]

VARIANTS = {
    "基准 V3":
        "[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "R1 桥碳不连氧":
        "[O:1]=[C:2]~[#6;!$([#6]~[OX1]):5]~[#6;!$([#6]~[OX1]):6]~[C:3]=[O:4]"
        ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "R2 桥碳不连杂原子":
        "[O:1]=[C:2]~[#6;!$([#6]~[!#6]):5]~[#6;!$([#6]~[!#6]):6]~[C:3]=[O:4]"
        ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "R3 两端碳也不连氧":
        "[O:1]=[C;!$([#6]~[OX1]):2]~[#6:5]~[#6:6]~[C;!$([#6]~[OX1]):3]=[O:4]"
        ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
}


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败 {str(e)[:40]}"
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return "底物解析失败"
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"异常 {str(e)[:40]}"
    if not res:
        return "无产物"
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


for label, sm in VARIANTS.items():
    print(f"\n{'=' * 100}\n【{label}】\n  {sm}\n{'=' * 100}")
    ok = 0
    for name, sub, expect in SHOULD:
        out = run(sm, sub)
        good = expect in out
        ok += good
        print(f"  {'✓' if good else '✗'} 应中 {name:<12} 期望{expect:<10} {out}")
    for name, sub in SHOULD_NOT:
        out = run(sm, sub)
        good = out == "无产物"
        ok += good
        print(f"  {'✓' if good else '✗'} 应排 {name:<20} {out}")
    print(f"  → {ok}/{len(SHOULD) + len(SHOULD_NOT)}")
