# -*- coding: utf-8 -*-
r"""最终解法：反应物侧用环闭合强制「两个 C=O 在同一个六元环里」。

诊断结论：
    对苯醌 / 9,10-蒽醌 ：两个 C=O 碳【共处同一个六元环】
    甾体 3,6-二酮      ：两个 C=O 碳在两个【不同】的环里

所以用环闭合 []1...[]1 把六个原子锁在同一个环里即可区分。
★ 但要【只加在反应物侧】——
   之前把环闭合也写进产物侧，RDKit 就不敢判定芳香性，产物分子式全错。
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
    ("邻苯醌（属邻位规则）", "O=C1C=CC=CC1=O"),
    ("四氢邻苯二甲酸酐（五元环）", "O=C1OC(=O)C2CCCC12"),
    ("邻苯二甲酸酐", "O=C1OC(=O)c2ccccc21"),
    ("乙酸酐", "CC(=O)OC(C)=O"),
    ("甾体3,6-二酮（两个不同环）",
     "CC[C@H](CC[C@@H](C)[C@H]1CC[C@@H]2[C@@]1(CC[C@H]3[C@@H]2CC(=O)C4[C@]3(CCC(=O)C4)C)C)C(C)C"),
]

VARIANTS = {
    "R5 现状（r6 + R）":
        "[O:1]=[C;r6:2]~[#6;R:5]~[#6;R:6]~[C;r6:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "R9 反应物环闭合":
        "[O:1]=[C;r6:2]1~[#6;R:5]~[#6;R:6]~[C;r6:3](=[O:4])~[#6]~[#6]1"
        ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "R10 反应物环闭合(不写r6)":
        "[O:1]=[C:2]1~[#6;R:5]~[#6;R:6]~[C:3](=[O:4])~[#6]~[#6]1"
        ">>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
}


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return "编译失败 " + str(e)[:40]
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return "底物解析失败"
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return "异常 " + str(e)[:40]
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
    for n, s, e in SHOULD:
        o = run(sm, s)
        g = e in o
        ok += g
        print(f"  {'✓' if g else '✗'} 应中 {n:<12} 期望{e:<10} {o}")
    for n, s in SHOULD_NOT:
        o = run(sm, s)
        g = o == "无产物"
        ok += g
        print(f"  {'✓' if g else '✗'} 应排 {n:<22} {o}")
    print(f"  → {ok}/{len(SHOULD) + len(SHOULD_NOT)}")
