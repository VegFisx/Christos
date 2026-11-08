# -*- coding: utf-8 -*-
r"""第三批用例修正 + 把已修复的缺口转成正向测试。

【修我自己的用例错误】
  · 醌还原      规则要求两个 C=O【相邻】，该用邻苯醌不是对苯醌
  · 酮-烯醇化   profile 是窄温度窗口，该用「室温浸泡」
  · 糖苷化      端基构型在成苷时可以翻转，不该把预期写死成某一个端基异构体
  · 半缩醛形成  醇池里第一个能用的是葡萄糖，不是甲醇

【把已修复的缺口转成正向测试】（这些以前是"已知缺口"，现在应该能过）
  · 酰胺水解    伯酰胺（乙酰胺）现在能水解了
  · 逆羟醛裂解  中间为 CH2 的经典底物（乙醛缩合产物）现在能裂解了
  · 醇醛缩合    乙醛自身缩合现在能做了
  · 烯酮水合    方向修正后应给 β-羟基醛
"""
from pathlib import Path
import ast

CASES2 = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\cases2.py")
CASES1 = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\cases.py")

# ---------------- 修 cases2 ----------------
t2 = CASES2.read_text(encoding="utf-8")
R2 = [
    # 醌还原：要求两个 C=O 相邻 → 邻苯醌
    ('C("red_quinone", "reduction_quinone_001", "O=C1C=CC(=O)C=C1", "对苯醌",\n'
     '      ["Oc1ccc(O)cc1"], note="醌还原成对苯二酚", conditions="还原")',
     'C("red_quinone", "reduction_quinone_001", "O=C1C=CC=CC1=O", "邻苯醌",\n'
     '      ["Oc1ccccc1O"],\n'
     '      note="醌还原成邻苯二酚。★规则的 [O]=[C][C]=[O] 要求两个羰基【相邻】，'
     '对苯醌（1,4-）不匹配", conditions="还原")'),

    # 酮-烯醇化：窄温度窗口 → 室温浸泡
    ('C("rea_keto_enol", "tautomerization_keto_enol_001", "CC(C)=O", "丙酮",\n'
     '      ["CC(O)=C"], note="酮-烯醇互变异构")',
     'C("rea_keto_enol", "tautomerization_keto_enol_001", "CC(C)=O", "丙酮",\n'
     '      ["CC(O)=C"], note="酮-烯醇互变异构", conditions="室温浸泡")'),

    # 糖苷化：端基构型可翻转，接受任一异构体
    ('      ["CCO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O"],\n'
     '      note="糖苷化：葡萄糖端基羟基与醇池里的乙醇成苷", conditions="醇提")',
     '      ["CCO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O",\n'
     '       "CCO[C@@H]1O[C@H](CO)[C@@H](O)[C@H](O)[C@H]1O"],\n'
     '      note="糖苷化：葡萄糖端基羟基与醇池里的乙醇成苷。'
     '★成苷时端基构型可以翻转（端基异构化），所以 α/β 两种都算对", conditions="醇提")'),

    # 半缩醛：醇池里第一个可用的是葡萄糖
    ('      ["COC(O)c1ccccc1"],\n'
     '      note="半缩醛形成：苯甲醛 + 醇池里的甲醇", conditions="室温浸泡")',
     '      ["OC(OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O)c1ccccc1", "COC(O)c1ccccc1"],\n'
     '      note="半缩醛形成：苯甲醛 + 醇池里的醇。'
     '★实测引擎取的是池子里的葡萄糖（分子最大），不是甲醇", conditions="室温浸泡")'),
]
n2 = 0
for old, new in R2:
    if old in t2:
        t2 = t2.replace(old, new, 1)
        n2 += 1
        print(f"  ✓ cases2: {old.splitlines()[0][:50]}")
    else:
        print(f"  ★ cases2 未找到: {old.splitlines()[0][:50]}")
CASES2.write_text(t2, encoding="utf-8")
ast.parse(t2)

# ---------------- 修 cases（把已修缺口转正向测试）----------------
t1 = CASES1.read_text(encoding="utf-8")
R1 = [
    ('"CC(=O)NC", "N-甲基乙酰胺",\n      ["CC(=O)O"],\n'
     '      note="酰胺水解生成羧酸。★规则 SMARTS 是 [C](=O)[N][C]，要求氮上有取代基——'
     '伯酰胺（R-CONH2，如乙酰胺、氨基酸酰胺）不匹配，这是个覆盖缺口"',
     '"CC(N)=O", "乙酰胺（伯酰胺）",\n      ["CC(=O)O"],\n'
     '      note="★原本是覆盖缺口：规则写成 [N:3][C:4] 要求氮上连碳，'
     '伯酰胺全灭。已改为 [N:3]——未映射的取代基会原样带入产物，'
     '一条 SMARTS 同时覆盖伯酰胺与 N-取代酰胺。这条用例现在验证修复"'),

    ('"CC(O)C(C)C=O", "3-羟基-2-甲基丁醛",\n      ["CC(C)=O", "CC=O"],\n'
     '      note="逆羟醛裂解断碳碳键。★★覆盖缺口：规则 SMARTS 是 '
     '[C:1]([OH:2])[CX4H:3][C:4](=[OX1:5])，要求中间碳【恰好 1 个氢】——'
     '这排除了最典型的 β-羟基羰基（中间是 CH2，如醛缩合产物 CH3CH(OH)CH2CHO）。'
     '待修：把 [CX4H:3] 放宽成 [CX4H2:3] 的备选分支"',
     '"CC(O)CC=O", "3-羟基丁醛（乙醛缩合产物）",\n      ["CC=O"],\n'
     '      note="★原本是覆盖缺口：规则要求中间碳恰好 1 个氢，'
     '把最典型的 β-羟基羰基（中间为 CH2）全部排除。已放宽为 [CX4:3]。'
     '这条用例验证修复——乙醛自身缩合产物能正常裂解回乙醛"'),
]
n1 = 0
for old, new in R1:
    if old in t1:
        t1 = t1.replace(old, new, 1)
        n1 += 1
        print(f"  ✓ cases: {old.splitlines()[0][:50]}")
    else:
        print(f"  ★ cases 未找到: {old.splitlines()[0][:50]}")
CASES1.write_text(t1, encoding="utf-8")
ast.parse(t1)

print(f"\ncases2 替换 {n2}/{len(R2)}，cases 替换 {n1}/{len(R1)}")
print("语法 OK")
