# -*- coding: utf-8 -*-
r"""修胺类的氢数写死（第 5 次同类问题）。

★★ 累计：「氢数写死」已经第 5 次 ★★
    1. 逆羟醛裂解  [CX4H:3]    排除中间为 CH2 的底物
    2. 醇醛缩合    [CX4H2:3]   排除乙醛
    3. 酮-烯醇化   [CX4H2:3]   排除丙酮
    4. 脱水        [CH2:1][CH1:2]  排除乙醇等伯醇
    5. 胺类三条    [NX3H2]     只认伯胺，排除仲胺

【本次】
    Michael加成(胺) / 酯的氨解 / 酰胺化(分子间) 都写成 [NX3H2:..][#6:..]，
    即「氮上 2 个氢 + 1 个碳」= 只认伯胺。

    但这三类反应化学上【伯胺、仲胺都能做】：
      · Michael 加成：伯胺仲胺均可
      · 酯的氨解：伯胺、仲胺均可
      · 酰胺化：伯胺、仲胺均可
    仲胺在中药成分（生物碱）里非常常见。

    修法：[NX3H2:5] → [NX3;H1,H2:5]（允许 1 个或 2 个氢）
"""
import json
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

FIX = {
    "addition_michael_amine_001": (
        "[C:1]=[C:2][C:3]=[OX1:4].[NX3;H1,H2:5][#6:6]"
        ">>[CX4:1]([N:5][#6:6])[CX4:2][C:3]=[OX1:4]",
        "伯胺、仲胺"),
    "aminolysis_ester_001": (
        "[C:1](=[O:2])[O:3]!@[C:4].[NX3;H1,H2:5][#6:6]"
        ">>[C:1](=[O:2])[N:5][#6:6].[O:3][C:4]",
        "伯胺、仲胺"),
    "amidation_intermolecular_001": (
        "[CX3:1](=[OX1:2])[OX2H:3].[NX3;H1,H2:4][#6:5]"
        ">>[C:1](=[O:2])[N:4][#6:5].[OH2:3]",
        "伯胺、仲胺"),
}

# 各自的测试底物（第一反应物, 第二反应物）
TESTS = {
    "addition_michael_amine_001": [
        ("丙烯醛 + 甲胺（伯胺）", "C=CC=O", "CN"),
        ("丙烯醛 + 二甲胺（仲胺）", "C=CC=O", "CNC"),
    ],
    "aminolysis_ester_001": [
        ("乙酸甲酯 + 甲胺（伯胺）", "COC(C)=O", "CN"),
        ("乙酸甲酯 + 二甲胺（仲胺）", "COC(C)=O", "CNC"),
    ],
    "amidation_intermolecular_001": [
        ("乙酸 + 甲胺（伯胺）", "CC(=O)O", "CN"),
        ("乙酸 + 二甲胺（仲胺）", "CC(=O)O", "CNC"),
    ],
}


def run(smarts, s1, s2):
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return [f"(编译失败 {e})"]
    m1, m2 = Chem.MolFromSmiles(s1), Chem.MolFromSmiles(s2)
    try:
        res = rxn.RunReactants((m1, m2))
    except Exception as e:
        return [f"(异常 {str(e)[:50]})"]
    outs = set()
    for ps in res[:3]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(Chem.MolToSmiles(pc))
            except Exception:
                fr.append("(非法)")
        outs.add(" + ".join(sorted(fr)))
    return sorted(outs)


print("=" * 96)
for rid, (new, scope) in FIX.items():
    r = by_id.get(rid)
    if r is None:
        print(f"[跳过] {rid}")
        continue
    old = r["smarts"]
    print(f"\n【{r['name']}】适用：{scope}")
    print(f"  旧: {old}")
    print(f"  新: {new}")
    for label, sm, s1, s2 in (("旧", old, None, None), ("新", new, None, None)):
        pass
    for label, smarts in (("旧", old), ("新", new)):
        print(f"   {label}:")
        for name, s1, s2 in TESTS[rid]:
            res = run(smarts, s1, s2)
            mark = "✓" if res and not res[0].startswith("(") else "✗"
            print(f"     {mark} {name:<26} {res[:1] if res else '(无)'}")
    r["smarts"] = new
    r["notes"] = (r.get("notes", "") +
                  f" 【覆盖修复】原 [NX3H2:..] 要求氮上恰好 2 个氢 = 只认【伯胺】，"
                  f"把仲胺（中药生物碱里很常见）排除了。已改为 [NX3;H1,H2:..]，"
                  f"覆盖伯胺与仲胺。这是「氢数写死」的第 5 次：逆羟醛裂解、醇醛缩合、"
                  f"酮-烯醇化、脱水、胺类三条。")
    print(f"   → 已应用")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print()
print("=" * 96)
print("复核：其余氢数约束是否有意为之")
print("=" * 96)
print("""
  合理的（氢数是【官能团定义】的一部分，保留）：
    · 醛氧化      [CH1:1]=[O:2]        醛碳就是 1 个氢
    · 席夫碱生成   [CX3H1:1]=[OX1:2]    同上
    · 半缩醛形成   [CX3H1:1]=[OX1:2]    同上
    · 硫代半缩醛   [CX3H1:1]=[OX1:2]    同上
    · 醛还原成醇   [CX3H1:1]=[OX1:2]    同上
    · 伯醇氧化成醛  [CX4H2:1][OH:2]     伯醇碳就是 2 个氢
    · 羟基氧化    [CH1:1][OH:2]        仲醇碳就是 1 个氢
    · 脱甲基      [O:1][CH3:2]         O-甲基
    · 酰胺脱水成腈  [NX3H2:3]          伯酰胺 R-CONH2
    · 分子内酰胺化  [NX3H2:6]          γ-氨基丁酸型
    · 半缩醛水解   [CX4H1:1]           半缩醛碳
    · 缩醛水解    [CX4H1:1]           缩醛碳
    · 糖苷化      [CX4H1:1]           端基碳
    · 亚胺水解    [CX3H1:1]=[NX2:2]     醛亚胺

  待观察（可能过窄，但影响面小）：
    · 美拉德简化   [CH2:3]             要求 α-羟基醛的羟甲基
    · 胺氧化      [CX4H2:1][NX3H2:2]   要求伯胺且邻碳是 CH2
    · 氧化脱氨成羰基 同上
""")
print(f"规则总数 {len(data['rules'])}")
