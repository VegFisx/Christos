# -*- coding: utf-8 -*-
r"""收紧「对醌」规则的约束：把非醌的 1,4-二羰基排除掉。

★ 问题
  [O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4] 里的 ~ 太宽松，
  把酸酐（O=C-O-C=O）和普通 1,4-二酮也匹配了，产物还配不平。

  校验器抓到的两个反例：
    · 1,3-isobenzofurandione,3a,4,7,7a-tetrahydro-   ← 酸酐
    · 22-dihydrostigmast-4-en-3,6-dione             ← 1,4-二酮

★ 真正的醌应当满足
  两个 C=O 碳【都在环上】，且【C=O 的碳之间由环碳相连】。
  试几种约束，找能排除酸酐/二酮、又保住苯醌/萘醌/蒽醌的。
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

SHOULD_MATCH = [
    ("对苯醌", "O=C1C=CC(=O)C=C1", "C6H6O2"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "C10H8O2"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "C14H10O2"),
    ("大黄素", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O", "C15H12O6"),
    ("辅酶Q0型", "CC1=CC(=O)C(C)=CC1=O", "C8H10O2"),
]
SHOULD_NOT = [
    ("邻苯醌（属邻位规则）", "O=C1C=CC=CC1=O"),
    ("四氢邻苯二甲酸酐（酸酐）", "O=C1OC(=O)C2CCCC12"),
    ("22-二氢豆甾-4-烯-3,6-二酮（1,4-二酮）",
     "CC(C)C(CC[C@H](C)C1CC[C@@]2(C)C3CC[C@]4(C)C(C)(C)CCC4CC3=CC(=O)C12C)C"),
]

VARIANTS = {
    "V3 基准（~）":
        "[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "V4 环内键 @":
        "[O:1]=[C:2]@[#6:5]@[#6:6]@[C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "V5 两端碳在环上":
        "[O:1]=[C;R:2]~[#6:5]~[#6:6]~[C;R:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "V6 三碳都在环上":
        "[O:1]=[C;R:2]~[#6;R:5]~[#6;R:6]~[C;R:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
    "V7 环内键 + 两端在环":
        "[O:1]=[C;R:2]@[#6:5]@[#6:6]@[C;R:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]",
}


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return None, f"编译失败 {str(e)[:34]}"
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return None, "底物解析失败"
    nm = len(m.GetSubstructMatches(rxn.GetReactantTemplate(0)))
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return nm, f"异常 {str(e)[:30]}"
    if not res:
        return nm, "无产物"
    outs = set()
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
        outs.add(" + ".join(fr))
    return nm, " ؛ ".join(outs)


for label, sm in VARIANTS.items():
    print(f"\n{'=' * 100}\n【{label}】{sm}\n{'=' * 100}")
    ok = 0
    for name, sub, expect in SHOULD_MATCH:
        _nm, out = run(sm, sub)
        good = expect in (out or "")
        ok += good
        print(f"  {'✓' if good else '✗'} 应匹配 {name:<14} 期望 {expect:<10} {out}")
    print("  --- 不该匹配的 ---")
    for name, sub in SHOULD_NOT:
        _nm, out = run(sm, sub)
        good = "无产物" in (out or "")
        ok += good
        print(f"  {'✓' if good else '✗'} 应排除 {name:<28} {out}")
    print(f"  → {ok}/{len(SHOULD_MATCH) + len(SHOULD_NOT)}")
