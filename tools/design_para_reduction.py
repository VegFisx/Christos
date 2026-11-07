# -*- coding: utf-8 -*-
r"""还原方向（对醌 → 对二酚）的变体筛选。

氧化方向已经确定用变体 A：
    [OH:1][c:2][c:5][c:6][c:3][OH:4]>>[O:1]=[C:2][c:5][c:6][C:3]=[O:4]
    对苯二酚/1,4-萘二酚/蒽氢醌 全部正确

还原方向第一版对苯醌匹配不上。逐个变体定位原因。
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

SUBS = [
    ("对苯醌", "O=C1C=CC(=O)C=C1"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21"),
    ("邻苯醌（不该管）", "O=C1C=CC=CC1=O"),
]

VARIANTS = {
    "1 原来的": "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "2 用 [C:] 而非 [#6:]": "[O:1]=[C:2][C:5][C:6][C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "3 产物显式闭环": "[O:1]=[C:2]1[C:5][C:6][C:3](=[O:4])[cH][cH]1>>[OH:1][c:2]1[c:5][c:6][c:3]([OH:4])[cH][cH]1",
    "4 反应物显式闭环(6元)": "[O:1]=[C:2]1[C:5][C:6][C:3](=[O:4])[#6][#6]1>>[OH:1][c:2]1[c:5][c:6][c:3]([OH:4])[#6][#6]1",
    "5 反应物不闭环": "[O:1]=[C:2]([#6])[#6:5][#6:6][C:3](=[O:4])[#6]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
}


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败: {str(e)[:40]}"
    m = Chem.MolFromSmiles(sub)
    patt = rxn.GetReactantTemplate(0)
    n_match = len(m.GetSubstructMatches(patt)) if m is not None else -1
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"模板匹配{n_match}，运行异常 {str(e)[:34]}"
    if not res:
        return f"模板匹配{n_match}，但无产物"
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
    return f"模板匹配{n_match} → " + " ؛ ".join(out)


for label, sm in VARIANTS.items():
    print(f"\n{'=' * 96}")
    print(f"【{label}】{sm}")
    print("=" * 96)
    for name, sub in SUBS:
        print(f"  {name:<20} {run(sm, sub)}")
