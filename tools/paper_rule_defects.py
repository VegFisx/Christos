# -*- coding: utf-8 -*-
r"""
论文 TableS1 规则的问题清单 —— 逐条给出可复现的演示
====================================================

★ 这是本轮最重要的产出

  `docs/supplementary/TableS1_reaction_rules.csv` 是发表时用的规则表。
  拿它跟"它自己写的说明"对照，会发现若干条**说不出通**：

    名字说"水解为羧酸+醇"，SMARTS 却匹配不上酚酯
    名字说"脱羧释放 CO2"，SMARTS 的产物里根本没有 CO2
    名字说"隐含水合"，加水的方向却是反的

  本脚本对每条可疑规则给出：
    · 论文原始 SMARTS
    · 一个能暴露问题的具体底物
    · 论文版跑出来的结果
    · 修正版跑出来的结果

  全部可复现，不靠断言。
"""

import csv
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
from rdkit.Chem.rdMolDescriptors import CalcMolFormula

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

PAPER = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")

paper = {}
with PAPER.open(encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        paper[row["规则名"].strip()] = row


def run(smarts, sub, co=None):
    """跑一条 SMARTS，返回产物字符串（含分子式）。"""
    try:
        rxn = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        return f"编译失败: {e}"
    m = Chem.MolFromSmiles(sub)
    if m is None:
        return "底物解析失败"
    mols = [m]
    if co:
        m2 = Chem.MolFromSmiles(co)
        if m2 is None:
            return "第二反应物解析失败"
        mols.append(m2)
    try:
        res = rxn.RunReactants(tuple(mols))
    except Exception as e:
        return f"运行异常: {str(e)[:60]}"
    if not res:
        return "(不匹配 / 无产物)"
    outs = []
    for ps in res[:2]:
        fr = []
        for p in ps:
            pc = Chem.Mol(p)
            try:
                Chem.SanitizeMol(pc)
                fr.append(f"{Chem.MolToSmiles(pc)} [{CalcMolFormula(pc)}]")
            except Exception:
                fr.append("(价态非法)")
        outs.append(" + ".join(fr))
    return " ؛ ".join(dict.fromkeys(outs))


# 每条：论文SMARTS、修正SMARTS、演示底物、为什么
CASES = [
    ("β-酮酸脱羧",
     "乙酰乙酸（论文说明是「脱羧释放 CO2」）", "CC(=O)CC(=O)O",
     "[CX3:1](=[OX1:2])[CX4:3][CX3:4](=[OX1:5])[OH:6]>>[CX3:1](=[OX1:2])[CX4:3]",
     "[CX3:1](=[OX1:2])[CX4:3][CX3:4](=[OX1:5])[OH:6]>>[CX3:1](=[OX1:2])[CX4:3].[C](=[O])=[O]",
     "论文版的产物只到 [CX4:3] 就结束了 —— CO2 那一份根本没写。"
     "脱羧却不产 CO2，等于把碳和氧凭空扔掉（原子不守恒）。"),

    ("缩醛水解",
     "苯甲醛二甲缩醛（缩醛水解应给醛 + 两个醇）", "COC(OC)c1ccccc1",
     "[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]>>[CX3H1:1]=[OX1:2].[OH:4][#6:5]",
     "[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]>>[CX3H1:1]=[OX1:2].[OH:4][#6:5].[OH][#6:3]",
     "缩醛 R-CH(OR')(OR'') 水解应给 醛 + R'OH + R''OH 三个产物。"
     "论文版只写了其中一个醇，另一个（[#6:3] 那一侧）整块丢了。"),

    ("醌还原",
     "邻苯醌（论文说明是「邻醌还原为邻苯二酚」）", "O=C1C=CC=CC1=O",
     "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][C:2][C:3][OH:4]",
     "[O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]",
     "碳氧双键变单键后，C2/C3 各补 1 个氢 → 产物成了环己二烯二醇 C6H8O2。"
     "邻苯二酚应该是【芳香】的 C6H6O2。"),

    ("α,β-不饱和羰基水合",
     "丙烯醛（α,β-不饱和羰基水合＝Michael 型，水应加到 β碳）", "C=CC=O",
     "[C:1]=[C:2][C:3]=[O:4]>>[C:1][C:2]([OH])[C:3]=[O:4]",
     "[C:1]=[C:2][C:3]=[O:4]>>[C:1]([OH])[C:2][C:3]=[O:4]",
     "论文版把羟基因在了 α碳(C2) 上，得到乳醛 CC(O)C=O。"
     "正确应加在 β碳，得 3-羟基丙醛 O=CCCO。"),

    ("糖苷水解",
     "水杨苷（酚苷 —— 中药里绝大多数糖苷是这一类）",
     "C1=CC=C(C(=C1)CO)O[C@H]2[C@@H]([C@H]([C@@H]([C@H](O2)CO)O)O)O",
     "[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][C:8]"
     ">>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][C:8]",
     "[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][#6:8]"
     ">>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][#6:8]",
     "SMARTS 里 [C] 专指【脂肪碳】。酚苷的苷元碳是芳香碳，匹配不上。"
     "结果这条规则对中药里最常见的糖苷类型【完全无效】。"),

    ("酯水解",
     "乙酸苯酯（酚酯 —— 酚酸酯在中药里很常见）", "CC(=O)Oc1ccccc1",
     "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]",
     "[C:1](=[O:2])[O:3][#6:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]",
     "同上：[C:4] 只认脂肪碳，酚酯全不匹配。"),

    ("酰胺水解",
     "乙酰胺（伯酰胺 R-CONH2，论文说明是「酰胺水解为羧酸+胺」）", "CC(N)=O",
     "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[O:3][H].[N:3][C:4]",
     "[C:1](=[O:2])[N:3]>>[C:1](=[O:2])[OH].[N:3]",
     "论文版要求氮上必须连碳，伯酰胺（乙酰胺、谷氨酰胺、天冬酰胺）全灭。"
     "另外产物写成 [O:3][H] —— 借用了酰胺氧的编号当羟基氧，映射不对。"),

    ("脱水",
     "乙醇（醇脱水成烯最基础的例子）", "CCO",
     "[CH2:1][CH1:2][OH:3]>>[C:1]=[C:2].[OH2]",
     "[CX4:1][CX4:2][OX2H:3]>>[C:1]=[C:2].[OH2]",
     "论文版要求羟基碳恰好 1 个氢、邻碳恰好 2 个氢 —— 乙醇两个条件都不满足。"),

    ("酮-烯醇化",
     "丙酮（论文说明是「酮/醛的 α-H 烯醇化」）", "CC(C)=O",
     "[CX3:1](=[OX1:2])[CX4H2:3]>>[C:1]([OH:2])=[C:3]",
     "[CX3:1](=[OX1:2])[CX4:3]>>[C:1]([OH:2])=[C:3]",
     "论文版要求 α碳恰好 2 个氢 —— 丙酮的 α碳是 CH3，匹配不上。"),

    ("脱甲基",
     "乙酸甲酯（不是芳香甲醚，不该被「脱甲基」）", "COC(C)=O",
     "[O:1][CH3:2]>>[O:1][H].[CH3][OH]",
     "[c:3][O:1][CH3:2]>>[c:3][O:1][H].[CH3][OH]",
     "论文版的 [O:1][CH3:2] 会命中一切 O-CH3。"
     "乙酸甲酯/苯甲酸甲酯/甲基葡萄糖苷都被它「脱甲基」，"
     "但那些其实是酯水解/糖苷水解该干的事——同一转化被两条规则重复计算。"),

    ("胺氧化",
     "乙胺（伯胺氧化）", "CCN",
     "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O:2].[NH3]",
     "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O].[N:2]",
     "论文版产物写成 .[NH3] 且把映射号给了元素符号 [O:2]；"
     "现行版把氨写成 [N:2] 并保留映射。属于写法修正，匹配范围不变。"),
]

print("=" * 108)
print("论文 TableS1 规则问题清单（全部可复现）")
print("=" * 108)

n_real = 0
for name, desc, sub, old, new, why in CASES:
    row = paper.get(name)
    print(f"\n{'─' * 108}")
    print(f"【{name}】论文里的说明：{row['说明'] if row else '(未找到)'}")
    print(f"  演示底物：{desc}")
    print(f"    {sub}")
    print(f"  论文 SMARTS：{old}")
    print(f"    跑出来 → {run(old, sub)}")
    print(f"  现行 SMARTS：{new}")
    print(f"    跑出来 → {run(new, sub)}")
    print(f"  ★ 问题：{why}")

print()
print("=" * 108)
print("分类")
print("=" * 108)
print("""
  原子不守恒（凭空丢原子）：
    · β-酮酸脱羧    CO2 那一份没写
    · 缩醛水解      其中一个醇没写

  产物结构错（原子数对得上，结构不对）：
    · 醌还原        产物没芳香化，分子式多 2 个氢
    · α,β-不饱和羰基水合   加成方向反了

  整类底物漏匹配：
    · 糖苷水解      酚苷全不匹配（中药糖苷绝大多数是酚苷）
    · 酯水解        酚酯不匹配
    · 酰胺水解      伯酰胺不匹配

  过窄（最典型底物不匹配）：
    · 脱水          乙醇不匹配
    · 酮-烯醇化      丙酮不匹配

  过宽（抢了别的规则的活）：
    · 脱甲基        命中一切 O-CH3，重复计算酯水解/糖苷水解

  写法问题（不影响行为）：
    · 酰胺水解      产物借用了 [O:3] 当羟基氧
    · 胺氧化        产物写成 [NH3]，映射号位置不对
""")
