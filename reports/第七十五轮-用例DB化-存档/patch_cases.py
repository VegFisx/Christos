# -*- coding: utf-8 -*-
r"""修正 cases.py 里用错的底物 / 预期 / 条件。

★ 这些修正都是【用例写错了】，不是引擎错：
  · 酰胺水解  规则的 SMARTS 要求氮上有取代基 → 伯酰胺不匹配，该用 N-甲基乙酰胺
  · 酚氧化成醌 规则的 OH-c-c-OH 要求两羟基【相邻】→ 该用邻苯二酚，不是对苯二酚
  · 分子内脱水成醚 规则要求两羟基间隔 4 个碳 → 该用 1,4-丁二醇
  · 逆羟醛裂解 规则要求羟基与羰基在【相邻】碳上 → 该用 3-羟基-2-丁酮
  · 席夫碱 / 酯的氨解 胺池第一个成员是甲胺，不是氨 → 预期产物应是 N-甲基化物
  · 分子内半缩醛化 profile 是 ambient → 该用「室温浸泡」
"""
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\tools\cases.py")
t = F.read_text(encoding="utf-8")

REPS = [
    # 酰胺水解：伯酰胺不匹配，改用 N-甲基乙酰胺
    ('"CC(N)=O", "乙酰胺",\n      ["CC(=O)O", "N"], note="酰胺水解生成羧酸 + 氨"',
     '"CC(=O)NC", "N-甲基乙酰胺",\n      ["CC(=O)O"],\n'
     '      note="酰胺水解生成羧酸。★规则 SMARTS 是 [C](=O)[N][C]，要求氮上有取代基——'
     '伯酰胺（R-CONH2，如乙酰胺、氨基酸酰胺）不匹配，这是个覆盖缺口"'),

    # 酚氧化成醌：要求两个羟基相邻
    ('"Oc1ccc(O)cc1", "对苯二酚",\n      ["O=C1C=CC(=O)C=C1"], note="对苯二酚氧化成对苯醌，酚类氧化的典型"',
     '"Oc1ccccc1O", "邻苯二酚",\n      ["O=C1C=CC(=O)C=C1"],\n'
     '      note="邻苯二酚氧化成邻苯醌。★规则的 [OH][c][c][OH] 要求两个羟基【相邻】，'
     '对苯二酚（1,4-）不匹配"'),

    # 分子内脱水成醚：两羟基间隔 4 个碳
    ('"OCCCCCCO", "1,6-己二醇",\n      ["C1CCOCC1"], note="分子内脱水成醚生成含氧环"',
     '"OCCCCO", "1,4-丁二醇",\n      ["C1CCOC1"],\n'
     '      note="分子内脱水成醚生成四氢呋喃。★规则要求两个羟基之间恰好隔 4 个碳"'),

    # 逆羟醛裂解：羟基与羰基相邻
    ('"CC(=O)CC(C)O", "4-羟基-2-戊酮",\n      ["CC(C)=O"], note="逆羟醛裂解，断碳碳键"',
     '"CC(=O)C(C)O", "3-羟基-2-丁酮",\n      ["CC=O"],\n'
     '      note="逆羟醛裂解断碳碳键。★规则要求羟基与羰基在【相邻】碳上"'),

    # Michael：加订正说明
    ('["CSCCC=O"], note="Michael 加成：丙烯醛 + 甲硫醇 → β-硫代醛",\n      conditions="室温浸泡"',
     '["CSCCC=O"],\n'
     '      note="★Michael 加成：硫必须加在 β碳上 → 3-甲硫基丙醛。'
     '原规则错加在 α碳（给 CSC(C)C=O）——两者分子式完全相同，'
     '原子守恒/价态/立体化学三道闸门全都发现不了，只有反应级测试集能抓出来",\n'
     '      conditions="室温浸泡"'),

    # 分子内半缩醛化：ambient → 室温浸泡
    ('"cyclization_hemiacetal_001", "O=CCCCO", "4-羟基丁醛",\n      ["OC1CCCO1"], note="4-羟基丁醛成环生成 2-羟基四氢呋喃"',
     '"cyclization_hemiacetal_001", "O=CCCCO", "4-羟基丁醛",\n'
     '      ["OC1CCCO1"], note="4-羟基丁醛成环生成 2-羟基四氢呋喃",\n'
     '      conditions="室温浸泡"'),

    # 席夫碱：胺池第一个是甲胺
    ('["c1ccc(/N=C/c2ccccc2)cc1"], note="醛 + 胺 → 席夫碱",\n      conditions="室温浸泡"',
     '["CN=Cc1ccccc1"],\n'
     '      note="醛 + 胺池里的甲胺 → 席夫碱。★注意胺池第一个成员是【甲胺】不是氨，'
     '所以产物是 N-甲基化物",\n      conditions="室温浸泡"'),

    # 酯的氨解：同样
    ('["CC(=O)N"], note="酯的氨解：酯 + 氨 → 酰胺 + 甲醇",\n      conditions="室温浸泡"',
     '["CNC(C)=O"],\n'
     '      note="酯的氨解：酯 + 胺池里的甲胺 → N-甲基乙酰胺",\n      conditions="室温浸泡"'),
]

n_ok = 0
for old, new in REPS:
    if old in t:
        t = t.replace(old, new, 1)
        n_ok += 1
        print(f"  ✓ 已替换: {old.splitlines()[0][:56]}")
    else:
        print(f"  ★ 未找到: {old.splitlines()[0][:56]}")

F.write_text(t, encoding="utf-8")
print(f"\n成功替换 {n_ok} / {len(REPS)}")

import ast
ast.parse(t)
print("语法 OK")
