# -*- coding: utf-8 -*-
r"""对醌还原的最终解法：反应物侧用 ~ 匹配，产物侧用默认键芳香化。

推导过程：
  版本一（反应物/产物都用默认键）
      → 产物分子式正确（萘醌 C10H8O2 ✓ 蒽醌 C14H10O2 ✓）
      → 但对苯醌匹配不上（路径上有双键，默认键只认单键/芳香键）

  版本二（两侧都用 ~）
      → 全部匹配上了
      → 但产物分子式多 2 个氢（~ 让 RDKit 不敢判定芳香性，于是给碳补氢）

  版本三（反应物用 ~，产物用默认键）← 本脚本验证
      → 期望：全都匹配，且分子式正确
"""
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

RED_V1 = "[O:1]=[C:2][#6:5][#6:6][C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]"
RED_V2 = "[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2]~[c:5]~[c:6]~[c:3][OH:4]"
RED_V3 = "[O:1]=[C:2]~[#6:5]~[#6:6]~[C:3]=[O:4]>>[OH:1][c:2][c:5][c:6][c:3][OH:4]"

SUBS = [
    ("对苯醌（最基础）", "O=C1C=CC(=O)C=C1", "C6H4O2", "C6H6O2"),
    ("1,4-萘醌", "O=C1C=CC(=O)c2ccccc21", "C10H6O2", "C10H8O2"),
    ("9,10-蒽醌", "O=C1c2ccccc2C(=O)c2ccccc21", "C14H8O2", "C14H10O2"),
    ("大黄素（蒽醌）", "Cc1cc(O)c2c(c1)C(=O)c1c(C2=O)c(O)cc(O)c1O", "C15H10O6", "C15H12O6"),
    ("辅酶Q0型（甲基对醌）", "CC1=CC(=O)C(C)=CC1=O", "C8H8O2", "C8H10O2"),
    ("邻苯醌（不该管）", "O=C1C=CC=CC1=O", "C6H4O2", "—"),
]


def run(smarts, sub):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败 {str(e)[:36]}"
    m = Chem.MolFromSmiles(sub)
    nm = len(m.GetSubstructMatches(rxn.GetReactantTemplate(0)))
    try:
        res = rxn.RunReactants((m,))
    except Exception as e:
        return f"模板{nm} 异常 {str(e)[:30]}"
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


for label, sm in (("V1 两侧默认键", RED_V1),
                  ("V2 两侧 ~", RED_V2),
                  ("V3 反应物 ~ / 产物默认", RED_V3)):
    print(f"\n{'=' * 100}\n【{label}】{sm}\n{'=' * 100}")
    ok = 0
    for name, sub, ein, eout in SUBS:
        r = run(sm, sub)
        good = eout in r
        if good:
            ok += 1
        mark = "✓" if good else ("—" if eout == "—" and "无产物" in r else "✗")
        print(f"  {mark} {name:<22} 期望 {ein}→{eout}")
        print(f"      {r}")
    print(f"  → 命中 {ok}/{len(SUBS)}")
