# 论文规则表 vs 现规则库

- 论文 TableS1：23 条
- 现规则库：61 条

## SMARTS 未变（11 条）

| 论文名 | 现名 |
|---|---|
| 硫酸酯水解 | 硫酸酯水解 |
| 磷酸酯水解 | 磷酸酯水解 |
| 半缩醛水解 | 半缩醛水解 |
| 羟基氧化 | 羟基氧化 |
| 醛氧化 | 醛氧化 |
| 酚氧化成醌 | 酚氧化成醌 |
| 酮还原 | 酮还原 |
| 芳香酸脱羧 | 芳香酸脱羧 |
| 芳香环羟基化 | 芳香环羟基化 |
| 烯烃水合 | 烯烃水合 |
| 美拉德简化 | 美拉德简化 |

## SMARTS 已改（12 条）

### 酯水解
- 论文说明：酯键水解为羧酸 + 醇（乌头碱减毒关键）
- 论文 SMARTS：`[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]`
- 现行 SMARTS：`[C:1](=[O:2])[O:3][#6:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]`

### 糖苷水解
- 论文说明：糖苷键水解（皂苷脱糖）
- 论文 SMARTS：`[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][C:8]>>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][C:8]`
- 现行 SMARTS：`[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[O:7][#6:8]>>[C:1]1([O:2][C:3][C:4][C:5][C:6]1)[OH].[OH:7][#6:8]`

### 酰胺水解
- 论文说明：酰胺水解为羧酸 + 胺
- 论文 SMARTS：`[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[O:3][H].[N:3][C:4]`
- 现行 SMARTS：`[C:1](=[O:2])[N:3]>>[C:1](=[O:2])[OH].[N:3]`

### 缩醛水解
- 论文说明：缩醛水解为醛 + 醇
- 论文 SMARTS：`[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]>>[CX3H1:1]=[OX1:2].[OH:4][#6:5]`
- 现行 SMARTS：`[CX4H1:1]([OX2:2][#6:3])[OX2:4][#6:5]>>[CX3H1:1]=[OX1:2].[OH:4][#6:5].[OH][#6:3]`

### 胺氧化
- 论文说明：伯胺氧化为醛 + 氨（生物碱降解）
- 论文 SMARTS：`[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O:2].[NH3]`
- 现行 SMARTS：`[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O].[N:2]`

### 醌还原
- 论文说明：邻醌还原为邻苯二酚（丹参酮、大黄蒽醌等）
- 论文 SMARTS：`[O:1]=[C:2][C:3]=[O:4]>>[OH:1][C:2][C:3][OH:4]`
- 现行 SMARTS：`[O:1]=[C:2][C:3]=[O:4]>>[OH:1][c:2][c:3][OH:4]`

### 脱水
- 论文说明：醇脱水生成双键
- 论文 SMARTS：`[CH2:1][CH1:2][OH:3]>>[C:1]=[C:2].[OH2]`
- 现行 SMARTS：`[CX4:1][CX4:2][OX2H:3]>>[C:1]=[C:2].[OH2]`

### 脱甲基
- 论文说明：芳香甲氧基脱甲基（生成酚 + 甲醇）
- 论文 SMARTS：`[O:1][CH3:2]>>[O:1][H].[CH3][OH]`
- 现行 SMARTS：`[c:3][O:1][CH3:2]>>[c:3][O:1][H].[CH3][OH]`

### β-酮酸脱羧
- 论文说明：β-酮酸脱羧生成酮（有机酸降解）
- 论文 SMARTS：`[CX3:1](=[OX1:2])[CX4:3][CX3:4](=[OX1:5])[OH:6]>>[CX3:1](=[OX1:2])[CX4:3]`
- 现行 SMARTS：`[CX3:1](=[OX1:2])[CX4:3][CX3:4](=[OX1:5])[OH:6]>>[CX3:1](=[OX1:2])[CX4:3].[C](=[O])=[O]`

### α,β-不饱和羰基水合
- 论文说明：α,β-不饱和羰基隐含水合
- 论文 SMARTS：`[C:1]=[C:2][C:3]=[O:4]>>[C:1][C:2]([OH])[C:3]=[O:4]`
- 现行 SMARTS：`[C:1]=[C:2][C:3]=[O:4]>>[C:1]([OH])[C:2][C:3]=[O:4]`

### 酮-烯醇化
- 论文说明：酮/醛的 α-H 烯醇化（影响后续反应）
- 论文 SMARTS：`[CX3:1](=[OX1:2])[CX4H2:3]>>[C:1]([OH:2])=[C:3]`
- 现行 SMARTS：`[CX3:1](=[OX1:2])[CX4:3]>>[C:1]([OH:2])=[C:3]`

### 酯化
- 论文说明：分子内酯化（γ/δ-羟基酸 → 内酯）
- 论文 SMARTS：`[OX2H:1][CX4:2][CX3:3](=[OX1:4])[OX2H:5]>>[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1`
- 现行 SMARTS：`[OX2H:1][CX4:2][CX4:5][CX4:6][CX3:3](=[OX1:4])[OX2H:7]>>[O:1]1[CX4:2][CX4:5][CX4:6][CX3:3]1=[OX1:4].[OH2:7]`


## 现库新增（38 条）

- Michael加成(硫醇)（addition）
- Michael加成(胺)（addition）
- δ-内酯化（esterification）
- δ-羟基酸内酯化(备用)（cyclization）
- 丙二酸型脱羧（decarboxylation）
- 亚砜氧化成砜（oxidation）
- 亚砜还原成硫醚（reduction）
- 亚胺水解（hydrolysis）
- 伯醇氧化成醛（oxidation）
- 内酰胺开环（hydrolysis）
- 分子内半缩醛化（cyclization）
- 分子内羟醛缩合（condensation）
- 分子内脱水成醚（cyclization）
- 分子内酰胺化（cyclization）
- 半缩醛形成(分子间)（condensation）
- 双键位置异构（rearrangement）
- 双键加氢（reduction）
- 双键环氧化（oxidation）
- 差向异构化（rearrangement）
- 席夫碱生成（condensation）
- 氧化脱氨成羰基（elimination）
- 环氧化物开环成二醇（hydrolysis）
- 硝基还原成胺（reduction）
- 硫代半缩醛形成（addition）
- 硫醇偶联成二硫（oxidation）
- 硫醚氧化成亚砜（oxidation）
- 糖苷化（condensation）
- 肉桂酸型脱羧（decarboxylation）
- 脱氢成α,β-不饱和羰基（oxidation）
- 逆羟醛裂解（rearrangement）
- 酚酸脱羧成酚（decarboxylation）
- 酯交换（esterification）
- 酯化(分子间)（esterification）
- 酯的氨解（condensation）
- 酰胺化(分子间)（condensation）
- 酰胺脱水成腈（elimination）
- 醇醛缩合(分子间)（condensation）
- 醛还原成醇（reduction）
