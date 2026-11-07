# 第七十五轮 · 规则来源体检（ORD 真实反应实测）

> **做法**：把每条规则的 SMARTS 套到 ORD 真实记录的**反应物**上，生成产物经「去映射号 / 去显式 H / 去立体 / 拆片段」规范化，再与记录的真实产物比对。
> **product_match** = 生成片段与该记录真实产物有交集；**fired** = 规则至少生成过一个可解析产物。

## 口径（先看这段）

* 数据源：`D:\ProgramData\DSHNS\chemreact-staging\data\ord_reaction_index.jsonl`，共 1,770,980 行；按步长 29 等距抽样，实际扫描 **59,999** 条。
* 这是**前向试跑**，不是逆合成审计；ORD 记录未必是同一反应类型，所以 `fired` 多不代表规则对，只代表底物里存在可匹配子结构。
* 规则里的水/共试剂多为**隐含**（如水解规则不把 H2O 写成反应物），因此本审计只把规则套到记录的反应物列；这比方案 a 的模板签名更接近真实用法。
* 规范化忽略立体与显式 H；`product_match` 是**分子图相同**，不是条件/机理相同。
* 只给计数与样例，**不打分、不排序**；`rules.json` 原顺序。

## 总览

* 规则：**64** 条（{'论文修正': 11, '论文原样': 11, '自写新增': 42}）
* 至少 `fired` 一次：**62** 条
* 至少 `product_match` 一次：**51** 条
* 反应物解析失败：**0** 次；产物解析失败：**0** 次

### 条件覆盖（所有 product_match 记录）

| 规则 | 命中记录 | 温度 | 催化剂 | 溶剂 | 试剂 | 任一条件 |
|---|---:|---:|---:|---:|---:|---:|
| `hydrolysis_ester_001` 酯水解 | 2430 | 461 | 93 | 2162 | 0 | 2176 |
| `hydrolysis_glycoside_001` 糖苷水解 | 49 | 6 | 4 | 46 | 0 | 46 |
| `hydrolysis_amide_001` 酰胺水解 | 1675 | 217 | 143 | 1438 | 0 | 1462 |
| `hydrolysis_sulfate_001` 硫酸酯水解 | 8 | 3 | 0 | 7 | 0 | 7 |
| `hydrolysis_phosphate_001` 磷酸酯水解 | 5 | 1 | 0 | 5 | 0 | 5 |
| `hydrolysis_acetal_001` 缩醛水解 | 118 | 19 | 5 | 111 | 0 | 111 |
| `oxidation_hydroxyl_001` 羟基氧化 | 162 | 30 | 48 | 153 | 0 | 155 |
| `oxidation_aldehyde_001` 醛氧化 | 67 | 8 | 10 | 57 | 0 | 60 |
| `oxidation_amine_001` 胺氧化 | 10 | 2 | 1 | 8 | 0 | 8 |
| `reduction_ketone_001` 酮还原 | 474 | 125 | 29 | 441 | 0 | 444 |
| `elimination_dehydration_001` 脱水 | 121 | 33 | 9 | 96 | 0 | 104 |
| `demethylation_aromatic_001` 脱甲基 | 356 | 107 | 6 | 304 | 0 | 310 |
| `decarboxylation_aromatic_001` 芳香酸脱羧 | 22 | 10 | 4 | 18 | 0 | 21 |
| `decarboxylation_beta_keto_001` β-酮酸脱羧 | 10 | 6 | 2 | 8 | 0 | 9 |
| `hydroxylation_aromatic_001` 芳香环羟基化 | 17 | 7 | 2 | 11 | 0 | 13 |
| `hydration_alkene_001` 烯烃水合 | 40 | 11 | 4 | 33 | 0 | 35 |
| `tautomerization_keto_enol_001` 酮-烯醇化 | 1 | 0 | 0 | 1 | 0 | 1 |
| `esterification_gamma_lactone_001` γ-内酯化 | 1 | 0 | 0 | 0 | 0 | 0 |
| `maillard_simplified_001` 美拉德简化 | 4 | 2 | 0 | 3 | 0 | 3 |
| `oxidation_primary_alcohol_001` 伯醇氧化成醛 | 259 | 58 | 84 | 243 | 0 | 245 |
| `oxidation_sulfide_001` 硫醚氧化成亚砜 | 153 | 30 | 9 | 134 | 0 | 134 |
| `oxidation_epoxide_001` 双键环氧化 | 66 | 15 | 6 | 56 | 0 | 61 |
| `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基 | 24 | 2 | 1 | 19 | 0 | 19 |
| `reduction_aldehyde_001` 醛还原成醇 | 145 | 35 | 6 | 135 | 0 | 138 |
| `reduction_alkene_001` 双键加氢 | 370 | 28 | 281 | 344 | 0 | 360 |
| `reduction_nitro_001` 硝基还原成胺 | 1034 | 172 | 783 | 951 | 0 | 998 |
| `hydrolysis_epoxide_001` 环氧化物开环成二醇 | 6 | 1 | 1 | 5 | 0 | 5 |
| `hydrolysis_lactam_001` 内酰胺开环 | 1379 | 156 | 123 | 1188 | 0 | 1208 |
| `hydrolysis_imine_001` 亚胺水解 | 10 | 2 | 0 | 7 | 0 | 8 |
| `cyclization_hemiacetal_001` 分子内半缩醛化 | 1 | 0 | 1 | 1 | 0 | 1 |
| `cyclization_lactam_001` 分子内酰胺化 | 1 | 0 | 0 | 0 | 0 | 0 |
| `cyclization_ether_001` 分子内脱水成醚 | 5 | 2 | 0 | 4 | 0 | 4 |
| `isomerization_double_bond_001` 双键位置异构 | 14 | 2 | 2 | 8 | 0 | 9 |
| `isomerization_epimerization_001` 差向异构化 | 155 | 31 | 10 | 122 | 0 | 127 |
| `rearrangement_retro_aldol_001` 逆羟醛裂解 | 11 | 6 | 2 | 9 | 0 | 10 |
| `decarboxylation_malonic_001` 丙二酸型脱羧 | 10 | 6 | 2 | 8 | 0 | 9 |
| `elimination_deamination_001` 氧化脱氨成羰基 | 10 | 2 | 1 | 8 | 0 | 8 |
| `esterification_transesterification_001` 酯交换 | 164 | 28 | 32 | 127 | 0 | 139 |
| `esterification_intermolecular_001` 酯化(分子间) | 557 | 110 | 95 | 288 | 0 | 358 |
| `condensation_schiff_base_001` 席夫碱生成 | 52 | 4 | 6 | 43 | 0 | 45 |
| `amidation_intermolecular_001` 酰胺化(分子间) | 3034 | 350 | 181 | 1985 | 0 | 2001 |
| `aminolysis_ester_001` 酯的氨解 | 610 | 138 | 27 | 390 | 0 | 407 |
| `condensation_glycosylation_001` 糖苷化 | 1 | 1 | 0 | 0 | 0 | 1 |
| `addition_michael_thiol_001` Michael加成(硫醇) | 21 | 5 | 3 | 16 | 0 | 20 |
| `addition_michael_amine_001` Michael加成(胺) | 40 | 8 | 3 | 31 | 0 | 34 |
| `condensation_aldol_001` 醇醛缩合(分子间) | 36 | 15 | 2 | 30 | 0 | 30 |
| `elimination_amide_to_nitrile_001` 酰胺脱水成腈 | 54 | 18 | 2 | 48 | 0 | 48 |
| `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜 | 10 | 4 | 0 | 9 | 0 | 9 |
| `reduction_sulfoxide_001` 亚砜还原成硫醚 | 6 | 1 | 0 | 5 | 0 | 5 |
| `oxidation_diphenol_para_001` 对二酚氧化成醌 | 1 | 0 | 1 | 1 | 0 | 1 |
| `reduction_quinone_para_001` 对醌还原成二酚 | 5 | 0 | 1 | 4 | 0 | 4 |

## 逐条结果

| # | 规则 | 类别 | 状态 | 论文档位 | fired | product_match | run_errors | 首个命中 rid |
|---|---|---|---|---|---|---|---|---|
| 1 | `hydrolysis_ester_001` 酯水解 | hydrolysis | active | 论文修正 | 22709 | 2430 | 0 | ord-4f8eca8686f04fab850d92ff0dd05c7a |
| 2 | `hydrolysis_glycoside_001` 糖苷水解 | hydrolysis | active | 论文修正 | 339 | 49 | 0 | ord-cbf5b75d0c184a8f8de856d128b7a42f |
| 3 | `hydrolysis_amide_001` 酰胺水解 | hydrolysis | active | 论文修正 | 21034 | 1675 | 0 | ord-4564e7dbfb7f40f5b631cc194e2c0fe9 |
| 4 | `hydrolysis_sulfate_001` 硫酸酯水解 | hydrolysis | active | 论文原样 | 790 | 8 | 0 | ord-e251509fdc3047e78ec0d2f448c09308 |
| 5 | `hydrolysis_phosphate_001` 磷酸酯水解 | hydrolysis | active | 论文原样 | 398 | 5 | 0 | ord-ae8dd6821be14cf8bfebc5f3f6061984 |
| 6 | `hydrolysis_acetal_001` 缩醛水解 | hydrolysis | active | 论文修正 | 1105 | 118 | 0 | ord-cbf5b75d0c184a8f8de856d128b7a42f |
| 7 | `hydrolysis_hemiacetal_001` 半缩醛水解 | hydrolysis | active | 论文原样 | 73 | 0 | 0 | — |
| 8 | `oxidation_hydroxyl_001` 羟基氧化 | oxidation | active | 论文原样 | 3859 | 162 | 0 | ord-b42315623c35470285d0d24571e8ef9f |
| 9 | `oxidation_aldehyde_001` 醛氧化 | oxidation | active | 论文原样 | 5311 | 67 | 0 | ord-d3006829c64043e1abcf88cb05d868f9 |
| 10 | `oxidation_phenol_quinone_001` 酚氧化成醌 | oxidation | active | 论文原样 | 122 | 0 | 0 | — |
| 11 | `oxidation_amine_001` 胺氧化 | oxidation | active | 论文修正 | 3281 | 10 | 0 | ord-2f581446dccc4df89ac08939b0a8b4ad |
| 12 | `reduction_ketone_001` 酮还原 | reduction | active | 论文原样 | 40963 | 474 | 0 | ord-71d372ee817748b9b806f8449f71356b |
| 13 | `reduction_quinone_001` 醌还原 | reduction | active | 论文修正 | 117 | 0 | 0 | — |
| 14 | `elimination_dehydration_001` 脱水 | elimination | active | 论文修正 | 8298 | 121 | 0 | ord-f9f37bcdc3464a7d9848ba524564d05b |
| 15 | `demethylation_aromatic_001` 脱甲基 | demethylation | active | 论文修正 | 7811 | 356 | 0 | ord-e71cb2ebf2654d4ba5d844ad5a953bf8 |
| 16 | `decarboxylation_aromatic_001` 芳香酸脱羧 | decarboxylation | active | 论文原样 | 3850 | 22 | 0 | ord-576c5ee4192c4e758d0a419bcdb33e60 |
| 17 | `decarboxylation_beta_keto_001` β-酮酸脱羧 | decarboxylation | active | 论文修正 | 132 | 10 | 0 | ord-95502ebefab047a3bba5b5f44fb8a3bc |
| 18 | `hydroxylation_aromatic_001` 芳香环羟基化 | hydroxylation | active | 论文原样 | 54950 | 17 | 0 | ord-357e71c8313b4627985e801cce9d4fe8 |
| 19 | `hydration_alkene_001` 烯烃水合 | hydration | active | 论文原样 | 8009 | 40 | 0 | ord-633cc3b5081846cbb6054e23f6596b4f |
| 20 | `hydration_enone_001` α,β-不饱和羰基水合 | hydration | active | 论文修正 | 3513 | 0 | 0 | — |
| 21 | `tautomerization_keto_enol_001` 酮-烯醇化 | rearrangement | active | 论文修正 | 26921 | 1 | 0 | ord-4951b98718c7408589b4833f8edfb304 |
| 22 | `esterification_gamma_lactone_001` γ-内酯化 | esterification | active | 自写新增 | 54 | 1 | 0 | ord-85cc4cab3f1d42ce82dc8c02004fd3d2 |
| 23 | `esterification_delta_lactone_001` δ-内酯化 | esterification | active | 自写新增 | 27 | 0 | 0 | — |
| 24 | `maillard_simplified_001` 美拉德简化 | condensation | active | 论文原样 | 88 | 4 | 0 | ord-2087b1486f6a48f981fffd8967d691df |
| 25 | `oxidation_primary_alcohol_001` 伯醇氧化成醛 | oxidation | active | 自写新增 | 5480 | 259 | 0 | ord-e5daab64725749169af83e097ae14fc0 |
| 26 | `oxidation_sulfide_001` 硫醚氧化成亚砜 | oxidation | active | 自写新增 | 4928 | 153 | 0 | ord-fe2625ae595846f3b0c390e98d15bfa3 |
| 27 | `oxidation_epoxide_001` 双键环氧化 | oxidation | active | 自写新增 | 8009 | 66 | 0 | ord-2dd7331ef1cc450ca46ca7997db579d9 |
| 28 | `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基 | oxidation | active | 自写新增 | 15570 | 24 | 0 | ord-afcb54bcb171469d92f46f5b1b8abf8c |
| 29 | `oxidation_thiol_disulfide_001` 硫醇偶联成二硫 | oxidation | disabled | 自写新增 | 0 | 0 | 0 | — |
| 30 | `reduction_aldehyde_001` 醛还原成醇 | reduction | active | 自写新增 | 5311 | 145 | 0 | ord-ba5e0dbceb244edeabb972ef6039049c |
| 31 | `reduction_alkene_001` 双键加氢 | reduction | active | 自写新增 | 8009 | 370 | 0 | ord-bc6e6e4b092043918a2288ce8fa820b4 |
| 32 | `reduction_nitro_001` 硝基还原成胺 | reduction | disabled | 自写新增 | 5067 | 1034 | 0 | ord-67ec3bcdf85a4cd095b46cc07afa68ed |
| 33 | `hydrolysis_epoxide_001` 环氧化物开环成二醇 | hydrolysis | active | 自写新增 | 553 | 6 | 0 | ord-6e3d86e8e07f4b1785b641a51d6e2340 |
| 34 | `hydrolysis_lactam_001` 内酰胺开环 | hydrolysis | active | 自写新增 | 14942 | 1379 | 0 | ord-4564e7dbfb7f40f5b631cc194e2c0fe9 |
| 35 | `hydrolysis_imine_001` 亚胺水解 | hydrolysis | active | 自写新增 | 159 | 10 | 0 | ord-02ad6847fc13402b92a36af897275a7b |
| 36 | `cyclization_hemiacetal_001` 分子内半缩醛化 | cyclization | active | 自写新增 | 52 | 1 | 0 | ord-adb34929297e49359d06c1c1b69d311e |
| 37 | `cyclization_lactam_001` 分子内酰胺化 | cyclization | active | 自写新增 | 38 | 1 | 0 | ord-dcba436418164a518817851e06e91f94 |
| 38 | `cyclization_ether_001` 分子内脱水成醚 | cyclization | active | 自写新增 | 253 | 5 | 0 | ord-5a6a6dff933a4d7bb05e4e1f68e8b190 |
| 39 | `cyclization_lactone_delta_001` δ-羟基酸内酯化(备用) | cyclization | active | 自写新增 | 27 | 0 | 0 | — |
| 40 | `condensation_aldol_intra_001` 分子内羟醛缩合 | condensation | disabled | 自写新增 | 0 | 0 | 0 | — |
| 41 | `isomerization_double_bond_001` 双键位置异构 | rearrangement | active | 自写新增 | 1770 | 14 | 0 | ord-176b45e9afc84e84bb02aa42c5439953 |
| 42 | `isomerization_epimerization_001` 差向异构化 | rearrangement | disabled | 自写新增 | 3395 | 155 | 0 | ord-dbe896ef33d741a789d2585a245fe8e0 |
| 43 | `rearrangement_retro_aldol_001` 逆羟醛裂解 | rearrangement | active | 自写新增 | 842 | 11 | 0 | ord-95502ebefab047a3bba5b5f44fb8a3bc |
| 44 | `decarboxylation_malonic_001` 丙二酸型脱羧 | decarboxylation | active | 自写新增 | 132 | 10 | 0 | ord-95502ebefab047a3bba5b5f44fb8a3bc |
| 45 | `elimination_deamination_001` 氧化脱氨成羰基 | elimination | active | 自写新增 | 3281 | 10 | 0 | ord-2f581446dccc4df89ac08939b0a8b4ad |
| 46 | `elimination_decarboxylation_phenol_001` 酚酸脱羧成酚 | decarboxylation | disabled | 自写新增 | 98 | 0 | 0 | — |
| 47 | `esterification_transesterification_001` 酯交换 | esterification | active | 自写新增 | 7323 | 164 | 0 | ord-23a5242235f843fa9d331c47debf3305 |
| 48 | `esterification_intermolecular_001` 酯化(分子间) | esterification | active | 自写新增 | 13123 | 557 | 0 | ord-aefa3b74c30b479da2d952052a0e8df6 |
| 49 | `condensation_schiff_base_001` 席夫碱生成 | condensation | active | 自写新增 | 1258 | 52 | 0 | ord-ad367c0052f942b5b42ca2f28c63efc1 |
| 50 | `amidation_intermolecular_001` 酰胺化(分子间) | condensation | active | 自写新增 | 8678 | 3034 | 0 | ord-6484a284b0aa46eaae0c0af132625719 |
| 51 | `aminolysis_ester_001` 酯的氨解 | condensation | active | 自写新增 | 11665 | 610 | 0 | ord-2e03a241be2b4b53bf88ccfacb21967f |
| 52 | `condensation_glycosylation_001` 糖苷化 | condensation | active | 自写新增 | 73 | 1 | 0 | ord-00fd638c0d41464696bea49aa4c5a664 |
| 53 | `condensation_hemiacetal_001` 半缩醛形成(分子间) | condensation | active | 自写新增 | 2025 | 0 | 0 | — |
| 54 | `addition_michael_thiol_001` Michael加成(硫醇) | addition | active | 自写新增 | 80 | 21 | 0 | ord-beff670127204f91a07e6837e3ee54fa |
| 55 | `addition_michael_amine_001` Michael加成(胺) | addition | active | 自写新增 | 1905 | 40 | 0 | ord-37bf6db4682043d784aacf127e737472 |
| 56 | `condensation_aldol_001` 醇醛缩合(分子间) | condensation | active | 自写新增 | 26921 | 36 | 0 | ord-b89820f3efd14138aa3a6cb136df92cc |
| 57 | `addition_thiohemiacetal_001` 硫代半缩醛形成 | addition | active | 自写新增 | 88 | 0 | 0 | — |
| 58 | `elimination_amide_to_nitrile_001` 酰胺脱水成腈 | elimination | active | 自写新增 | 1440 | 54 | 0 | ord-72e7e9fd9d714797ab3b1ceb025540aa |
| 59 | `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜 | oxidation | active | 自写新增 | 1810 | 10 | 0 | ord-5505b5e667d847a0be6fa845705d47a2 |
| 60 | `reduction_sulfoxide_001` 亚砜还原成硫醚 | reduction | active | 自写新增 | 1810 | 6 | 0 | ord-40453b2cc8d74902b8ebe4e9a37f2d13 |
| 61 | `decarboxylation_cinnamic_001` 肉桂酸型脱羧 | decarboxylation | active | 自写新增 | 140 | 0 | 0 | — |
| 62 | `oxidation_diphenol_para_001` 对二酚氧化成醌 | oxidation | active | 自写新增 | 84 | 1 | 0 | ord-76b77f0e77ff4e818e609c821b2df0a5 |
| 63 | `reduction_quinone_para_001` 对醌还原成二酚 | reduction | active | 自写新增 | 169 | 5 | 0 | ord-ea2aaea7fcb84ecf97673d17fa69c1c4 |
| 64 | `esterification_paper_original_001` 酯化(论文原版·产物模板有误) | esterification | disabled | 自写新增 | 318 | 0 | 0 | — |

## 命中样例（前 3 条）

### `hydrolysis_ester_001` 酯水解

* `ord-4f8eca8686f04fab850d92ff0dd05c7a`
  * 反应物：`CCOC(=O)c1cc(CC)c2cc(N3CCN(C)CC3)ccn2c1=O + Cl + [Na+].[OH-]`
  * 生成命中：`CCc1cc(C(=O)O)c(=O)n2ccc(N3CCN(C)CC3)cc12`
  * 记录产物：`CCc1cc(C(=O)O)c(=O)n2ccc(N3CCN(C)CC3)cc12 ; CCc1cc(C(=O)O)c(=O)n2ccc(N3CCN(C)CC3)cc12.Cl ; Cl`
* `ord-2900eeef6bee4f96854b610d5c6665dc`
  * 反应物：`COC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2)cc1OC`
  * 生成命中：`COc1cc(C(=O)CN2CCN(c3ccncc3)CC2)ccc1OCC(=O)O`
  * 记录产物：`COc1cc(C(=O)CN2CCN(c3ccncc3)CC2)ccc1OCC(=O)O`
* `ord-1b1496d4ad5040759352f2bc285c5252`
  * 反应物：`CC(=O)O + CCOC(=O)c1cccc(Nc2ncc3cc(-c4c(Cl)cccc4Cl)c(=O)n(C)c3n2)c1 + [Na+].[OH-]`
  * 生成命中：`Cn1c(=O)c(-c2c(Cl)cccc2Cl)cc2cnc(Nc3cccc(C(=O)O)c3)nc21`
  * 记录产物：`Cn1c(=O)c(-c2c(Cl)cccc2Cl)cc2cnc(Nc3cccc(C(=O)O)c3)nc21`

### `hydrolysis_glycoside_001` 糖苷水解

* `ord-cbf5b75d0c184a8f8de856d128b7a42f`
  * 反应物：`COc1cccc(C(=O)N(CCOC2CCCCO2)c2ccccc2OC)c1 + Cc1ccc(S(=O)(=O)O)cc1.O + O=C([O-])O.[Na+]`
  * 生成命中：`COc1cccc(C(=O)N(CCO)c2ccccc2OC)c1`
  * 记录产物：`COc1cccc(C(=O)N(CCO)c2ccccc2OC)c1`
* `ord-5644e5fd1d534b5297d22337a4455595`
  * 反应物：`CCCCCCCCCCc1ccc(-c2ccc([C@H]3CC[C@H](OC4CCCCO4)CC3)cc2)cc1 + C[Si](C)(C)OS(=O)(=O)O[Si](C)(C)C + c1ccncc1`
  * 生成命中：`CCCCCCCCCCc1ccc(-c2ccc(C3CCC(O)CC3)cc2)cc1`
  * 记录产物：`CCCCCCCCCCc1ccc(-c2ccc(C3CCC(O)CC3)cc2)cc1`
* `ord-548a260dea404a5c8c1788cbebc98700`
  * 反应物：`FC(F)(F)COCCOC1CCCCO1 + [Br-].[Br-].[Mg+2]`
  * 生成命中：`OCCOCC(F)(F)F`
  * 记录产物：`OCCOCC(F)(F)F`

### `hydrolysis_amide_001` 酰胺水解

* `ord-4564e7dbfb7f40f5b631cc194e2c0fe9`
  * 反应物：`CC(=O)NC1CCN(c2ccncc2)CC1 + Cl`
  * 生成命中：`NC1CCN(c2ccncc2)CC1`
  * 记录产物：`Cl ; Cl.Cl.Cl.NC1CCN(c2ccncc2)CC1.O ; NC1CCN(c2ccncc2)CC1 ; O`
* `ord-29290da4f651485f9a89caa1ac100820`
  * 反应物：`COC(=O)Cn1c(C(=O)N[C@H](CCCCNC(=O)OCc2ccccc2)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
  * 生成命中：`COC(=O)Cn1c(C(=O)NC(CCCCN)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
  * 记录产物：`COC(=O)Cn1c(C(=O)NC(CCCCN)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
* `ord-546e985c373d49ba8a1bca6b63eaccc9`
  * 反应物：`CC(=O)Nc1nnc(S(N)(=O)=O)s1 + CC(=O)Nc1nnc(S(N)(=O)=O)s1.CC(N)=O + Cl`
  * 生成命中：`Nc1nnc(S(N)(=O)=O)s1`
  * 记录产物：`Nc1nnc(S(N)(=O)=O)s1`

### `hydrolysis_sulfate_001` 硫酸酯水解

* `ord-e251509fdc3047e78ec0d2f448c09308`
  * 反应物：`COS(=O)(=O)C(F)(F)F + O=C1CCSCC1`
  * 生成命中：`O=S(=O)(O)C(F)(F)F`
  * 记录产物：`CC1CC(=O)CCS1 ; CC1CC(=O)CCS1.O=S(=O)(O)C(F)(F)F ; O=S(=O)(O)C(F)(F)F`
* `ord-d7512c75706848f79c8959a5584299b7`
  * 反应物：`CCOc1ccccc1N + Cc1ccc(S(=O)(=O)OCC2CN(Cc3ccccc3)CCO2)cc1`
  * 生成命中：`Cc1ccc(S(=O)(=O)O)cc1`
  * 记录产物：`CCOc1ccccc1NCC1CN(Cc2ccccc2)CCO1 ; CCOc1ccccc1NCC1CN(Cc2ccccc2)CCO1.Cc1ccc(S(=O)(=O)O)cc1 ; Cc1ccc(S(=O)(=O)O)cc1`
* `ord-dcb304e604ec4edc8e6800498ca50bcc`
  * 反应物：`C=CC=C + CCCCCCCCCCCCOS(=O)(=O)[O-].[Na+]`
  * 生成命中：`CCCCCCCCCCCCO`
  * 记录产物：`CCCCCCCCCCCCO`

### `hydrolysis_phosphate_001` 磷酸酯水解

* `ord-ae8dd6821be14cf8bfebc5f3f6061984`
  * 反应物：`CC(=O)N[C@H]1[C@@H](OP(=O)(O)OP(=O)(O)OC[C@H]2O[C@@H](n3ccc(=O)[nH]c3=O)[C@H](O)[C@@H]2O)O[C@H](CO)[C@@H](O)[C@@H]1O + CC(=O)OCC(=O)N[C@H]1C(O)O[C@H](CO)[C@@H](O)[C@@H]1O.O=c1ccn([C@@H]2O[C@H](COP(=O)(O)OP(=O)(O)O)[C@@H](O)[C@H]2O)c(=O)[nH]1 + C[O-].[Na+] + O=C(Cc1ccc(-c2ccccc2)cc1)N[C@H]1C(O)O[C@H](CO)[C@@H](O)[C@@H]1O.O=c1ccn([C@@H]2O[C@H](COP(=O)(O)OP(=O)(O)O)[C@@H](O)[C@H]2O)c(=O)[nH]1`
  * 生成命中：`O=c1ccn(C2OC(COP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)[nH]1`
  * 记录产物：`O=C(CO)NC1C(O)OC(CO)C(O)C1O ; O=C(CO)NC1C(O)OC(CO)C(O)C1O.O=c1ccn(C2OC(COP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)[nH]1 ; O=c1ccn(C2OC(COP(=O)(O)OP(=O)(O)O)C(O)C2O)c(=O)[nH]1`
* `ord-a222735708e8494387c3f3d4802ef6d4`
  * 反应物：`CCOP(=O)(O)c1ccc(Cn2c(=O)c(=O)[nH]c3cc([N+](=O)[O-])ccc32)cc1 + O`
  * 生成命中：`O=c1[nH]c2cc([N+](=O)[O-])ccc2n(Cc2ccc(P(=O)(O)O)cc2)c1=O`
  * 记录产物：`O=c1[nH]c2cc([N+](=O)[O-])ccc2n(Cc2ccc(P(=O)(O)O)cc2)c1=O`
* `ord-fc50f6087af84196a118650dd7a74445`
  * 反应物：`CCO + CCOP(=O)(OCC)c1cc(F)ccc1CNC(=O)c1nc2n(c(=O)c1OCc1ccccc1)CCOC2(C)C + [Na+].[OH-]`
  * 生成命中：`CCOP(=O)(O)c1cc(F)ccc1CNC(=O)c1nc2n(c(=O)c1OCc1ccccc1)CCOC2(C)C`
  * 记录产物：`CCOP(=O)(O)c1cc(F)ccc1CNC(=O)c1nc2n(c(=O)c1OCc1ccccc1)CCOC2(C)C`

### `hydrolysis_acetal_001` 缩醛水解

* `ord-cbf5b75d0c184a8f8de856d128b7a42f`
  * 反应物：`COc1cccc(C(=O)N(CCOC2CCCCO2)c2ccccc2OC)c1 + Cc1ccc(S(=O)(=O)O)cc1.O + O=C([O-])O.[Na+]`
  * 生成命中：`COc1cccc(C(=O)N(CCO)c2ccccc2OC)c1`
  * 记录产物：`COc1cccc(C(=O)N(CCO)c2ccccc2OC)c1`
* `ord-5644e5fd1d534b5297d22337a4455595`
  * 反应物：`CCCCCCCCCCc1ccc(-c2ccc([C@H]3CC[C@H](OC4CCCCO4)CC3)cc2)cc1 + C[Si](C)(C)OS(=O)(=O)O[Si](C)(C)C + c1ccncc1`
  * 生成命中：`CCCCCCCCCCc1ccc(-c2ccc(C3CCC(O)CC3)cc2)cc1`
  * 记录产物：`CCCCCCCCCCc1ccc(-c2ccc(C3CCC(O)CC3)cc2)cc1`
* `ord-9ad38bc707b046e69c350290cb8d3501`
  * 反应物：`COC(CCn1cc(-c2cccnc2C#N)c(=O)[nH]c1=O)OC + O`
  * 生成命中：`N#Cc1ncccc1-c1cn(CCC=O)c(=O)[nH]c1=O`
  * 记录产物：`N#Cc1ncccc1-c1cn(CCC=O)c(=O)[nH]c1=O`

### `oxidation_hydroxyl_001` 羟基氧化

* `ord-b42315623c35470285d0d24571e8ef9f`
  * 反应物：`COCOCC(O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl + CS(C)=O + O=C(Cl)C(=O)Cl`
  * 生成命中：`COCOCC(=O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl`
  * 记录产物：`COCOCC(=O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl`
* `ord-df35b2df9c34402fb24e1439996fd691`
  * 反应物：`CC(C)=O.O=S(=O)(O)O.[O]=[Cr](=[O])=[O] + CC(C)O + CCOC(=O)CC(O)[C@@H]1CCCN1C(=O)CCC(=O)N(C)Cc1ccccc1 + O`
  * 生成命中：`CCOC(=O)CC(=O)C1CCCN1C(=O)CCC(=O)N(C)Cc1ccccc1`
  * 记录产物：`CCOC(=O)CC(=O)C1CCCN1C(=O)CCC(=O)N(C)Cc1ccccc1`
* `ord-fb7270a74cbc4031b8e83c2f70138da2`
  * 反应物：`CCN(CC)CC + CS(C)=O + Cc1ccc(CN2CCC(O)CC2)cc1 + O=C(Cl)C(=O)Cl`
  * 生成命中：`Cc1ccc(CN2CCC(=O)CC2)cc1`
  * 记录产物：`Cc1ccc(CN2CCC(=O)CC2)cc1`

### `oxidation_aldehyde_001` 醛氧化

* `ord-d3006829c64043e1abcf88cb05d868f9`
  * 反应物：`CC(C)=O.O=S(=O)(O)O.[O]=[Cr](=[O])=[O] + O=Cc1cc(F)ccc1Oc1ccc(Cl)c(Cl)c1`
  * 生成命中：`O=C(O)c1cc(F)ccc1Oc1ccc(Cl)c(Cl)c1`
  * 记录产物：`O=C(O)c1cc(F)ccc1Oc1ccc(Cl)c(Cl)c1`
* `ord-3d5e398ed2a04ef081f57c6cbf8e141e`
  * 反应物：`CC=C(C)C + Cc1[nH]c(C=O)nc1C(F)(F)F + O=P([O-])(O)O.[Na+] + [Na+].[O-][Cl+][O-]`
  * 生成命中：`Cc1[nH]c(C(=O)O)nc1C(F)(F)F`
  * 记录产物：`Cc1[nH]c(C(=O)O)nc1C(F)(F)F`
* `ord-ba12f7c9db334e34bcaddd916fc3ddf8`
  * 反应物：`COc1ccc(C2CC2CC=O)cc1F + [Na+].[OH-]`
  * 生成命中：`COc1ccc(C2CC2CC(=O)O)cc1F`
  * 记录产物：`COc1ccc(C2CC2CC(=O)O)cc1F`

### `oxidation_amine_001` 胺氧化

* `ord-2f581446dccc4df89ac08939b0a8b4ad`
  * 反应物：`CC(C)(C)OC(=O)N[C@H](CCCNC(=N)N[N+](=O)[O-])C(=O)O + CCN(CC)CC + CN(C)C(On1nnc2ccccc21)=[N+](C)C.F[B-](F)(F)F + Cl.NCCc1ccc(O)cc1`
  * 生成命中：`N`
  * 记录产物：`CC(C)(C)OC(=O)NC(CCCNC(N)=N[N+](=O)[O-])C(=O)NCCc1ccc(O)cc1 ; N`
* `ord-fc70462efd6c45659e9169b8717b2d49`
  * 反应物：`C1N2CN3CN1CN(C2)C3 + CC(C)(C)c1cc(CN)c(O)c(S(C)(=O)=O)c1.Cl + Cl + O=C(O)C(F)(F)F`
  * 生成命中：`CC(C)(C)c1cc(C=O)c(O)c(S(C)(=O)=O)c1`
  * 记录产物：`CC(C)(C)c1cc(C=O)c(O)c(S(C)(=O)=O)c1`
* `ord-e2471430116d4b988ea6326d8d16cab5`
  * 反应物：`COC(=O)C(F)F + ClCCl + NCCO`
  * 生成命中：`N`
  * 记录产物：`N ; O=C(NCCO)C(F)F`

### `reduction_ketone_001` 酮还原

* `ord-71d372ee817748b9b806f8449f71356b`
  * 反应物：`CC(C)[O-].CC(C)[O-].CC(C)[O-].[Al+3] + CCCC(=O)c1noc(COc2ccc(Cl)cc2Cl)n1`
  * 生成命中：`CCCC(O)c1noc(COc2ccc(Cl)cc2Cl)n1`
  * 记录产物：`CCCC(O)c1noc(COc2ccc(Cl)cc2Cl)n1`
* `ord-ec56bca52c65474f938fae5cfb0fea03`
  * 反应物：`CCCCCCCCCCCC1CC(=O)[C@@H](CCCCCC)C(=O)O1`
  * 生成命中：`CCCCCCCCCCCC1CC(O)C(CCCCCC)C(=O)O1`
  * 记录产物：`CCCCCCCCCCCC1CC(O)C(CCCCCC)C(=O)O1`
* `ord-ba5e0dbceb244edeabb972ef6039049c`
  * 反应物：`CC(C)(C)c1cc(C=Cc2cc(C=O)cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)c2)cc(C(C)(C)C)c1 + [BH4-].[Na+]`
  * 生成命中：`CC(C)(C)c1cc(C=Cc2cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)cc(CO)c2)cc(C(C)(C)C)c1`
  * 记录产物：`CC(C)(C)c1cc(C=Cc2cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)cc(CO)c2)cc(C(C)(C)C)c1`

### `elimination_dehydration_001` 脱水

* `ord-f9f37bcdc3464a7d9848ba524564d05b`
  * 反应物：`C/C(=C\C(=O)OCCCCCCCCC(=O)O)C[C@@H]1OC[C@H](C[C@@H]2O[C@H]2[C@@H](C)[C@H](C)O)[C@@H](O)[C@H]1O + CCCCC(CC)C(=O)[O-].[Ca]`
  * 生成命中：`O`
  * 记录产物：`CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O ; CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O.CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O.O.O.[Ca+2] ; O ; [Ca+2]`
* `ord-0587bcd743a44314873c72b7692035b6`
  * 反应物：`CCCCCCC(C)(C)c1ccc(C2CN(Cc3ccccc3)CCC2(O)CCCc2ccccc2)c(OCc2ccccc2)c1 + O=S(Cl)Cl`
  * 生成命中：`CCCCCCC(C)(C)c1ccc(C2=C(CCCc3ccccc3)CCN(Cc3ccccc3)C2)c(OCc2ccccc2)c1`
  * 记录产物：`CCCCCCC(C)(C)c1ccc(C2=C(CCCc3ccccc3)CCN(Cc3ccccc3)C2)c(OCc2ccccc2)c1`
* `ord-a982bb2edb894c5b8a8ffea19d4a0a2b`
  * 反应物：`O=P([O-])([O-])[O-].[Al+3] + OC1CCc2ccccc21`
  * 生成命中：`C1=Cc2ccccc2C1`
  * 记录产物：`C1=Cc2ccccc2C1`

### `demethylation_aromatic_001` 脱甲基

* `ord-e71cb2ebf2654d4ba5d844ad5a953bf8`
  * 反应物：`CCCCC12CCC(=O)C(C)=C1c1ccc(OC)c(Cl)c1C2 + Cl.c1ccncc1`
  * 生成命中：`CCCCC12CCC(=O)C(C)=C1c1ccc(O)c(Cl)c1C2`
  * 记录产物：`CCCCC12CCC(=O)C(C)=C1c1ccc(O)c(Cl)c1C2`
* `ord-4492a1316c2143eaaae289f2e539a4d5`
  * 反应物：`CCCCC12CCC(=O)C(C#N)=C1c1ccc(OC)c(Cl)c1C2 + Cl.c1ccncc1`
  * 生成命中：`CCCCC12CCC(=O)C(C#N)=C1c1ccc(O)c(Cl)c1C2`
  * 记录产物：`CCCCC12CCC(=O)C(C#N)=C1c1ccc(O)c(Cl)c1C2`
* `ord-7700df5685184235ac02c3c0c47a1faa`
  * 反应物：`BrB(Br)Br.ClCCl + CCOC(C)=O + COc1cc(C)cc(C)c1-c1cccc2c(N(CC3CC3)CC3CC3)c(SC)nn12`
  * 生成命中：`CSc1nn2c(-c3c(C)cc(C)cc3O)cccc2c1N(CC1CC1)CC1CC1`
  * 记录产物：`CSc1nn2c(-c3c(C)cc(C)cc3O)cccc2c1N(CC1CC1)CC1CC1`

### `decarboxylation_aromatic_001` 芳香酸脱羧

* `ord-576c5ee4192c4e758d0a419bcdb33e60`
  * 反应物：`O=C(O)c1cc2c(Br)cccc2s1 + c1ccc2ncccc2c1`
  * 生成命中：`Brc1cccc2sccc12`
  * 记录产物：`Brc1cccc2sccc12`
* `ord-40409f7fad30481a8741d4469a92a16e`
  * 反应物：`CCCCCCCCN(CCCCCCCC)CCCCCCCC + COC(=O)c1c(F)c(F)c(F)c(F)c1C(=O)O`
  * 生成命中：`COC(=O)c1cc(F)c(F)c(F)c1F`
  * 记录产物：`COC(=O)c1cc(F)c(F)c(F)c1F`
* `ord-15da0e0e90c04472b92bb81c71f5ffc3`
  * 反应物：`CCCCCCCCN(CCCCCCCC)CCCCCCCC + COc1c(F)c(F)c(C(=O)O)c(C(=O)O)c1F + [Na+].[OH-]`
  * 生成命中：`COc1c(F)c(F)cc(C(=O)O)c1F`
  * 记录产物：`COc1c(F)c(F)cc(C(=O)O)c1F`

### `decarboxylation_beta_keto_001` β-酮酸脱羧

* `ord-95502ebefab047a3bba5b5f44fb8a3bc`
  * 反应物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4C(C(=O)O)C(=O)O)nc2n(CCC)c1=O + [K+].[OH-]`
  * 生成命中：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
  * 记录产物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
* `ord-5c76c4a7daf5438cab96058325b857ae`
  * 反应物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)O)C(=O)OCC + C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)OCC)C(=O)OCC`
  * 生成命中：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
  * 记录产物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
* `ord-5573c3af085c4ad39e195fab14b73779`
  * 反应物：`O + O=C(O)C(CC1=Cc2ccccc21)C(=O)O`
  * 生成命中：`O=C(O)CCC1=Cc2ccccc21`
  * 记录产物：`O=C(O)CCC1=Cc2ccccc21`

### `hydroxylation_aromatic_001` 芳香环羟基化

* `ord-357e71c8313b4627985e801cce9d4fe8`
  * 反应物：`CCC(=O)O + O=O + O=c1n(O)c(=O)n(O)c(=O)n1O + c1ccc2c(c1)Cc1ccccc1-2`
  * 生成命中：`Oc1cccc2c1Cc1ccccc1-2`
  * 记录产物：`O=C1C=CC=C2C1=Cc1ccccc12 ; Oc1cccc2c1Cc1ccccc1-2`
* `ord-f710a7defa434541bd08ad7bd7b5c832`
  * 反应物：`CCOP(=S)(S)OCC + N#Cc1c(O)cccc1O + NC(=S)c1ccccc1O`
  * 生成命中：`NC(=S)c1c(O)cccc1O`
  * 记录产物：`NC(=S)c1c(O)cccc1O`
* `ord-9ffbf3e2cc744c9dacaade74a2f8b70e`
  * 反应物：`CC(C)[N-]C(C)C.[Li+] + COB(OC)OC + Fc1cccc(F)n1`
  * 生成命中：`Oc1ccc(F)nc1F`
  * 记录产物：`Oc1ccc(F)nc1F`

### `hydration_alkene_001` 烯烃水合

* `ord-633cc3b5081846cbb6054e23f6596b4f`
  * 反应物：`B + C=CCCCCC(COCCCCCCCCCCCCCCCC)OC + OO + [Na+].[OH-]`
  * 生成命中：`CCCCCCCCCCCCCCCCOCC(CCCCCCO)OC`
  * 记录产物：`CCCCCCCCCCCCCCCCOCC(CCCCCCO)OC`
* `ord-bc2ecd447f7046cb8c4b9417b2b75f91`
  * 反应物：`B1C2CCCC1CCC2 + C=C1CC(c2ncc3c(Cl)nccn23)C1 + O + [Cl-].[Na+]`
  * 生成命中：`OCC1CC(c2ncc3c(Cl)nccn23)C1`
  * 记录产物：`OCC1CC(c2ncc3c(Cl)nccn23)C1`
* `ord-8232eecacf3b455bbc2945e59598b458`
  * 反应物：`B1C2CCCC1CCC2 + C=C1CC(c2nc(-c3ccc4ccc(-c5ccccc5)nc4c3)c3c(Cl)nccn23)C1 + OO + [Na+].[OH-]`
  * 生成命中：`OCC1CC(c2nc(-c3ccc4ccc(-c5ccccc5)nc4c3)c3c(Cl)nccn23)C1`
  * 记录产物：`OCC1CC(c2nc(-c3ccc4ccc(-c5ccccc5)nc4c3)c3c(Cl)nccn23)C1`

### `tautomerization_keto_enol_001` 酮-烯醇化

* `ord-4951b98718c7408589b4833f8edfb304`
  * 反应物：`CC(C)=O + COc1ccc(C#N)cc1C(=O)NCCN1CCC(C(=O)c2ccc(F)cc2)CC1 + [BH4-].[Na+]`
  * 生成命中：`COc1ccc(C#N)cc1C(=O)NCCN1CCC(=C(O)c2ccc(F)cc2)CC1`
  * 记录产物：`COc1ccc(C#N)cc1C(=O)NCCN1CCC(=C(O)c2ccc(F)cc2)CC1`

### `esterification_gamma_lactone_001` γ-内酯化

* `ord-85cc4cab3f1d42ce82dc8c02004fd3d2`
  * 反应物：`O=C(O)CCC(=O)c1ccc(Cl)c(Cl)c1 + O=C(O)CCC(O)c1ccc(Cl)c(Cl)c1 + O=C(O)CCC(c1ccccc1)c1ccc(Cl)c(Cl)c1`
  * 生成命中：`O=C1CCC(c2ccc(Cl)c(Cl)c2)O1`
  * 记录产物：`O=C1CCC(c2ccc(Cl)c(Cl)c2)O1`

### `maillard_simplified_001` 美拉德简化

* `ord-2087b1486f6a48f981fffd8967d691df`
  * 反应物：`CCC(=O)O + NCCN + O=C(O)CO + O=C([O-])CO`
  * 生成命中：`O=CC(=O)O`
  * 记录产物：`O=C(O)C(=O)O ; O=CC(=O)O`
* `ord-aed66271d5ba4168987a79c9a9109deb`
  * 反应物：`CCCC(=O)O + NCP(=O)(O)O + O=C(O)CO + O=C([O-])CO`
  * 生成命中：`O=CC(=O)[O-]`
  * 记录产物：`O=C([O-])C(=O)[O-] ; O=CC(=O)[O-] ; O=C[O-]`
* `ord-1cf2dfe722a54a6dbae12f375f50831c`
  * 反应物：`CCCC(=O)O + NCP(=O)(O)O + O=C(O)CO + O=C([O-])CO`
  * 生成命中：`O=CC(=O)[O-]`
  * 记录产物：`O=C([O-])C(=O)[O-] ; O=CC(=O)[O-] ; O=C[O-]`

### `oxidation_primary_alcohol_001` 伯醇氧化成醛

* `ord-e5daab64725749169af83e097ae14fc0`
  * 反应物：`CC(=O)OI1(OC(C)=O)(OC(C)=O)OC(=O)c2ccccc21 + CC(C)(C)OC(=O)N[C@@H](Cc1cccc(F)c1)[C@@H](CO)O[Si](C)(C)C(C)(C)C + ClCCl + c1ccncc1`
  * 生成命中：`CC(C)(C)OC(=O)NC(Cc1cccc(F)c1)C(C=O)O[Si](C)(C)C(C)(C)C`
  * 记录产物：`CC(C)(C)OC(=O)NC(Cc1cccc(F)c1)C(C=O)O[Si](C)(C)C(C)(C)C`
* `ord-741edcda20ec4dd68396b440300ebbef`
  * 反应物：`OCc1ccc(-c2cccc3cncn23)cc1`
  * 生成命中：`O=Cc1ccc(-c2cccc3cncn23)cc1`
  * 记录产物：`O=Cc1ccc(-c2cccc3cncn23)cc1`
* `ord-a2c21d1ff6fb48648d47adbb5018a845`
  * 反应物：`CC(C)(C)OC(=O)N1CCCC(CO)C1 + CCOCC`
  * 生成命中：`CC(C)(C)OC(=O)N1CCCC(C=O)C1`
  * 记录产物：`CC(C)(C)OC(=O)N1CCCC(C=O)C1`

### `oxidation_sulfide_001` 硫醚氧化成亚砜

* `ord-fe2625ae595846f3b0c390e98d15bfa3`
  * 反应物：`CCCC1(CCOc2ccnc(CSc3nc4ccccc4[nH]3)c2C)OCCO1 + CCOC(C)=O + O=C(OO)c1cccc(Cl)c1 + O=C([O-])O.[Na+]`
  * 生成命中：`CCCC1(CCOc2ccnc(CS(=O)c3nc4ccccc4[nH]3)c2C)OCCO1`
  * 记录产物：`CCCC1(CCOc2ccnc(CS(=O)c3nc4ccccc4[nH]3)c2C)OCCO1`
* `ord-949ee3ff62fd4c5ca41768ef2de67233`
  * 反应物：`C=CCOc1ccc(CSCCn2ccnn2)cc1 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`C=CCOc1ccc(CS(=O)CCn2ccnn2)cc1`
  * 记录产物：`C=CCOc1ccc(CS(=O)CCn2ccnn2)cc1`
* `ord-929afb9fe4594f40a99f8ed5337e8832`
  * 反应物：`COc1ccc2c(SCc3nnc4ccc(-c5ccccc5)nn34)ccnc2c1 + O=C(OO)c1cccc(Cl)c1 + O=C([O-])O.[Na+]`
  * 生成命中：`COc1ccc2c(S(=O)Cc3nnc4ccc(-c5ccccc5)nn34)ccnc2c1`
  * 记录产物：`CO ; CO.[NH4+].[OH-] ; COc1ccc2c(S(=O)Cc3nnc4ccc(-c5ccccc5)nn34)ccnc2c1 ; [NH4+] ; [OH-]`

### `oxidation_epoxide_001` 双键环氧化

* `ord-2dd7331ef1cc450ca46ca7997db579d9`
  * 反应物：`CC1(C)CC=CCO1 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC1(C)CC2OC2CO1`
  * 记录产物：`CC1(C)CC2OC2CO1`
* `ord-2841169aef9044f08240ff998112be18`
  * 反应物：`CC(C)(C)[Si](C)(C)O[C@H]1C=CC(=O)C1 + OO + [Na+].[OH-]`
  * 生成命中：`CC(C)(C)[Si](C)(C)OC1CC(=O)C2OC12`
  * 记录产物：`CC(C)(C)[Si](C)(C)OC1CC(=O)C2OC12`
* `ord-55e62b8b24c94c1da7be2e5d55ad708a`
  * 反应物：`C=C(C)[C@@]1(O)[C@H](Br)[C@H](OC(=O)NC(=O)CCl)CC[C@]12CO2 + CCCCCC.CCOC(C)=O + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC1(C2(O)C(Br)C(OC(=O)NC(=O)CCl)CCC23CO3)CO1`
  * 记录产物：`CC1(C2(O)C(Br)C(OC(=O)NC(=O)CCl)CCC23CO3)CO1`

### `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基

* `ord-afcb54bcb171469d92f46f5b1b8abf8c`
  * 反应物：`O + O=C(O)C(F)(F)F + O=C1CCc2ccc(OCCCCN3CCN(c4cccc(Cl)c4Cl)CC3)cc2N1 + [Na+].[OH-]`
  * 生成命中：`O=c1ccc2ccc(OCCCCN3CCN(c4cccc(Cl)c4Cl)CC3)cc2[nH]1`
  * 记录产物：`O=c1ccc2ccc(OCCCCN3CCN(c4cccc(Cl)c4Cl)CC3)cc2[nH]1`
* `ord-8b3e021b29204afdae23067a0e2ab230`
  * 反应物：`CC1CC(=O)NN=C1c1ccc(NN)cc1 + Cc1cc(=O)[nH]nc1-c1ccc(N)cc1`
  * 生成命中：`Cc1cc(=O)[nH]nc1-c1ccc(NN)cc1`
  * 记录产物：`Cc1cc(=O)[nH]nc1-c1ccc(NN)cc1`
* `ord-0cb26ae7b1b64fa3b2fddccdf0aaeeab`
  * 反应物：`BrBr + O=C1CCC(c2ccc(-n3ccnc3-c3ccccc3)cc2)=NN1`
  * 生成命中：`O=c1ccc(-c2ccc(-n3ccnc3-c3ccccc3)cc2)n[nH]1`
  * 记录产物：`O=c1ccc(-c2ccc(-n3ccnc3-c3ccccc3)cc2)n[nH]1`

### `reduction_aldehyde_001` 醛还原成醇

* `ord-ba5e0dbceb244edeabb972ef6039049c`
  * 反应物：`CC(C)(C)c1cc(C=Cc2cc(C=O)cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)c2)cc(C(C)(C)C)c1 + [BH4-].[Na+]`
  * 生成命中：`CC(C)(C)c1cc(C=Cc2cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)cc(CO)c2)cc(C(C)(C)C)c1`
  * 记录产物：`CC(C)(C)c1cc(C=Cc2cc(C=Cc3cc(C(C)(C)C)cc(C(C)(C)C)c3)cc(CO)c2)cc(C(C)(C)C)c1`
* `ord-2adf7b177715439eb19c5c872418961b`
  * 反应物：`NCc1ccccn1 + O=Cc1ccc(C=O)cc1 + [H][H]`
  * 生成命中：`O=Cc1ccc(CO)cc1`
  * 记录产物：`O=Cc1ccc(CO)cc1`
* `ord-1ce25ae06a494bf6ac544d70458fb12d`
  * 反应物：`C1CCOC1 + Cc1cc(OCC2(O)CCSCC2)cc(C)c1-c1cccc(C=O)c1 + [BH4-].[Na+]`
  * 生成命中：`Cc1cc(OCC2(O)CCSCC2)cc(C)c1-c1cccc(CO)c1`
  * 记录产物：`Cc1cc(OCC2(O)CCSCC2)cc(C)c1-c1cccc(CO)c1`

### `reduction_alkene_001` 双键加氢

* `ord-bc6e6e4b092043918a2288ce8fa820b4`
  * 反应物：`CC(=Cc1ccccc1)C(=O)O`
  * 生成命中：`CC(Cc1ccccc1)C(=O)O`
  * 记录产物：`CC(Cc1ccccc1)C(=O)O`
* `ord-75c8773115fe4b749a62c2b459df5ce2`
  * 反应物：`CCOC(=O)C=Cc1ccccc1CC#N`
  * 生成命中：`CCOC(=O)CCc1ccccc1CC#N`
  * 记录产物：`CCOC(=O)CCc1ccccc1CC#N`
* `ord-accbc80711cd4fed92cf4c23a8ce2cf4`
  * 反应物：`O=C(O)c1cccc(C=CCC2SCC(=O)N2CCC2(O)CCCCC2)c1 + [H][H]`
  * 生成命中：`O=C(O)c1cccc(CCCC2SCC(=O)N2CCC2(O)CCCCC2)c1`
  * 记录产物：`O=C(O)c1cccc(CCCC2SCC(=O)N2CCC2(O)CCCCC2)c1`

### `reduction_nitro_001` 硝基还原成胺

* `ord-67ec3bcdf85a4cd095b46cc07afa68ed`
  * 反应物：`Cc1c([N+](=O)[O-])ccc2c1C(=O)NS2(=O)=O + [H][H]`
  * 生成命中：`Cc1c(N)ccc2c1C(=O)NS2(=O)=O`
  * 记录产物：`Cc1c(N)ccc2c1C(=O)NS2(=O)=O`
* `ord-68a8e77da56c464fb8e4488b01b277d1`
  * 反应物：`Cc1cc(C#N)ccc1[N+](=O)[O-] + O=C([O-])O.[Na+] + [Cl][Sn][Cl]`
  * 生成命中：`Cc1cc(C#N)ccc1N`
  * 记录产物：`Cc1cc(C#N)ccc1N`
* `ord-53a3ebdf15d441468909b1e846bdef45`
  * 反应物：`O=[N+]([O-])c1ccc(Cl)cc1[N+](=O)[O-] + [NH4+]`
  * 生成命中：`Nc1cc(Cl)ccc1[N+](=O)[O-]`
  * 记录产物：`Nc1cc(Cl)ccc1[N+](=O)[O-]`

### `hydrolysis_epoxide_001` 环氧化物开环成二醇

* `ord-6e3d86e8e07f4b1785b641a51d6e2340`
  * 反应物：`COc1cc2c(Oc3cc4cnccc4nc3C)ccnc2cc1OCC1CO1 + O + O=C(O)C(F)(F)F + [Na+].[OH-]`
  * 生成命中：`COc1cc2c(Oc3cc4cnccc4nc3C)ccnc2cc1OCC(O)CO`
  * 记录产物：`COc1cc2c(Oc3cc4cnccc4nc3C)ccnc2cc1OCC(O)CO`
* `ord-a1c7bf51043e43aab9ac5c08ae5136df`
  * 反应物：`C1CO1 + Cc1ccc(S(=O)(=O)O)cc1.O + c1ccc(OCC2CO2)cc1 + c1ccc2c(c1)Nc1ccccc1S2`
  * 生成命中：`OCC(O)COc1ccccc1`
  * 记录产物：`OCC(O)COc1ccccc1`
* `ord-e593a00348594473b7d15918ded3aab0`
  * 反应物：`C1CO1 + CC(=O)Nc1ccc(O)cc1 + CC1CO1`
  * 生成命中：`CC(O)CO`
  * 记录产物：`CC(O)CO ; CC1CO1`

### `hydrolysis_lactam_001` 内酰胺开环

* `ord-4564e7dbfb7f40f5b631cc194e2c0fe9`
  * 反应物：`CC(=O)NC1CCN(c2ccncc2)CC1 + Cl`
  * 生成命中：`NC1CCN(c2ccncc2)CC1`
  * 记录产物：`Cl ; Cl.Cl.Cl.NC1CCN(c2ccncc2)CC1.O ; NC1CCN(c2ccncc2)CC1 ; O`
* `ord-29290da4f651485f9a89caa1ac100820`
  * 反应物：`COC(=O)Cn1c(C(=O)N[C@H](CCCCNC(=O)OCc2ccccc2)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
  * 生成命中：`COC(=O)Cn1c(C(=O)NC(CCCCN)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
  * 记录产物：`COC(=O)Cn1c(C(=O)NC(CCCCN)C(=O)NCCCCCc2c(OC)cc(C)cc2OC)cc2ccccc21`
* `ord-e90368ffd2234df394e85e5cab1a5b4f`
  * 反应物：`CC(C)(C)OC(=O)N1CC[C@H](NC(=O)CNC(=N)NC(=O)OCc2ccc([N+](=O)[O-])cc2)C1 + CC(C)OC(C)C + O=S(=O)(O)O`
  * 生成命中：`N=C(NCC(=O)NC1CCNC1)NC(=O)OCc1ccc([N+](=O)[O-])cc1`
  * 记录产物：`N=C(NCC(=O)NC1CCNC1)NC(=O)OCc1ccc([N+](=O)[O-])cc1 ; N=C(NCC(=O)NC1CCNC1)NC(=O)OCc1ccc([N+](=O)[O-])cc1.O=S(=O)(O)OS(=O)(=O)O ; O=S(=O)(O)OS(=O)(=O)O`

### `hydrolysis_imine_001` 亚胺水解

* `ord-02ad6847fc13402b92a36af897275a7b`
  * 反应物：`C=CCCC(N=Cc1ccccc1)C(=O)OC + Cl + O`
  * 生成命中：`C=CCCC(N)C(=O)OC`
  * 记录产物：`C=CCCC(N)C(=O)OC`
* `ord-f8efbab678334a79b2529d4e996099eb`
  * 反应物：`CCN(C=Nc1nc(Cl)c2[nH]cnc2n1)CC + CCN(C=O)CC + Clc1nc(N=CN2CCCCC2)nc2nc[nH]c12 + O=CN1CCCCC1`
  * 生成命中：`Nc1nc(Cl)c2[nH]cnc2n1`
  * 记录产物：`Nc1nc(Cl)c2[nH]cnc2n1`
* `ord-f4b79fcdd4274acc9f776993d7dd934b`
  * 反应物：`CCCCC(CC)(N=Cc1ccccc1)C(=O)OCC + Cl`
  * 生成命中：`CCCCC(N)(CC)C(=O)OCC`
  * 记录产物：`CCCCC(N)(CC)C(=O)OCC`

### `cyclization_hemiacetal_001` 分子内半缩醛化

* `ord-adb34929297e49359d06c1c1b69d311e`
  * 反应物：`C1=COCC1 + C=O + CC(CO)CCO + O=CCCCO`
  * 生成命中：`OC1CCCO1`
  * 记录产物：`O=CCCCO ; O=CCCCO.OC1CCCO1 ; OC1CCCO1`

### `cyclization_lactam_001` 分子内酰胺化

* `ord-dcba436418164a518817851e06e91f94`
  * 反应物：`C[C@H]1CNCCc2ccc(Cl)cc21.N[C@@H](CCC(=O)O)C(=O)O + O=C1CC[C@@H](C(=O)[O-])N1`
  * 生成命中：`O=C1CCC(C(=O)O)N1`
  * 记录产物：`CC1CNCCc2ccc(Cl)cc21 ; CC1CNCCc2ccc(Cl)cc21.O=C1CCC(C(=O)O)N1 ; O=C1CCC(C(=O)O)N1`

### `cyclization_ether_001` 分子内脱水成醚

* `ord-5a6a6dff933a4d7bb05e4e1f68e8b190`
  * 反应物：`C=CCCCCBr + Nc1[nH]c(=S)nc2c1ncn2[C@@H]1O[C@H](CO)[C@@H](O)[C@H]1O + [Na+].[OH-]`
  * 生成命中：`O`
  * 记录产物：`C=CCCCCSc1nc(N)c2ncn(C3OC(CO)C(O)C3O)c2n1 ; C=CCCCCSc1nc(N)c2ncn(C3OC(CO)C(O)C3O)c2n1.C=CCCCCSc1nc(N)c2ncn(C3OC(CO)C(O)C3O)c2n1.O ; O`
* `ord-96576426befc4e1bab12afd442deddbf`
  * 反应物：`CC(C)(C)OC(=O)N1CC(O)(CCCO)C1 + CC(C)(C)[O-].[K+] + Cc1ccc(S(=O)(=O)Cl)cc1 + O`
  * 生成命中：`CC(C)(C)OC(=O)N1CC2(CCCO2)C1`
  * 记录产物：`CC(C)(C)OC(=O)N1CC2(CCCO2)C1`
* `ord-3afaf30667084466b4316290c2cfe397`
  * 反应物：`CCCCCCC.CCOC(C)=O + CCCCCCCCc1ccc(C(O)CC(O)CO)cc1 + Cc1ccc(S(=O)(=O)O)cc1.O`
  * 生成命中：`CCCCCCCCc1ccc(C2CC(O)CO2)cc1`
  * 记录产物：`CCCCCCCCc1ccc(C2CC(O)CO2)cc1`

### `isomerization_double_bond_001` 双键位置异构

* `ord-176b45e9afc84e84bb02aa42c5439953`
  * 反应物：`O=C(O)CCCC/C=C\C1C=CCC1=O + [Na+].[OH-]`
  * 生成命中：`O=C(O)CCCCC=CC1=CCCC1=O`
  * 记录产物：`O=C(O)CCCCC=CC1=CCCC1=O`
* `ord-d927d5ea634d457d8cc5c5bf5686f327`
  * 反应物：`Clc1ccc(C2=CCN(CCCCn3cncn3)CC2)cc1 + O=C(O)/C=C/C(=O)O`
  * 生成命中：`Clc1ccc(C2=CCN(CCCCn3cncn3)CC2)cc1`
  * 记录产物：`Clc1ccc(C2=CCN(CCCCn3cncn3)CC2)cc1 ; Clc1ccc(C2=CCN(CCCCn3cncn3)CC2)cc1.O=C(O)C=CC(=O)O ; O=C(O)C=CC(=O)O`
* `ord-6786df77746b406e88d0fac8c456bf1b`
  * 反应物：`C1=CC2C(C1)[C@@H]1C=C[C@H]2C1 + O=C1OC(=O)C2C3C=CC(C3)C12`
  * 生成命中：`C1=CC2C3C=CC(C3)C2C1`
  * 记录产物：`C1=CC2C3C=CC(C3)C2C1 ; C1=CC2C3C=CC(C3)C2C1.O=C1OC(=O)C2C3C=CC(C3)C12 ; O=C1OC(=O)C2C3C=CC(C3)C12`

### `isomerization_epimerization_001` 差向异构化

* `ord-dbe896ef33d741a789d2585a245fe8e0`
  * 反应物：`O=C(O)/C=C\C(=O)O + OC1CN(CCCOCCc2ccc3sccc3c2)C1`
  * 生成命中：`OC1CN(CCCOCCc2ccc3sccc3c2)C1`
  * 记录产物：`O=C(O)C=CC(=O)O ; O=C(O)C=CC(=O)O.OC1CN(CCCOCCc2ccc3sccc3c2)C1 ; OC1CN(CCCOCCc2ccc3sccc3c2)C1`
* `ord-6961669486c8494bb2c3a3bdd60048e7`
  * 反应物：`CC(O)C(=O)O + N=C(N)Nc1nc(CSCCC(=N)NS(N)(=O)=O)cs1 + NC(=O)c1ccncc1`
  * 生成命中：`CC(O)C(=O)O`
  * 记录产物：`CC(O)C(=O)O ; CC(O)C(=O)O.NC(=O)c1ccncc1 ; NC(=O)c1ccncc1`
* `ord-46a2b70cb3774dc384354d92898d7d21`
  * 反应物：`OC1CCCC(OCc2ccccc2)C1`
  * 生成命中：`OC1CCCC(OCc2ccccc2)C1`
  * 记录产物：`OC1CCCC(OCc2ccccc2)C1`

### `rearrangement_retro_aldol_001` 逆羟醛裂解

* `ord-95502ebefab047a3bba5b5f44fb8a3bc`
  * 反应物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4C(C(=O)O)C(=O)O)nc2n(CCC)c1=O + [K+].[OH-]`
  * 生成命中：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
  * 记录产物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
* `ord-5c76c4a7daf5438cab96058325b857ae`
  * 反应物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)O)C(=O)OCC + C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)OCC)C(=O)OCC`
  * 生成命中：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
  * 记录产物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
* `ord-172d59195ca84b65b312cbb7f868d1cd`
  * 反应物：`C=C(Cl)COC(=O)C(O)C(O)C(=O)[O-] + [O-][I+3]([O-])([O-])O`
  * 生成命中：`C=C(Cl)COC(=O)C=O`
  * 记录产物：`C=C(Cl)COC(=O)C=O ; C=C(Cl)COC(=O)C=O.O ; O`

### `decarboxylation_malonic_001` 丙二酸型脱羧

* `ord-95502ebefab047a3bba5b5f44fb8a3bc`
  * 反应物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4C(C(=O)O)C(=O)O)nc2n(CCC)c1=O + [K+].[OH-]`
  * 生成命中：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
  * 记录产物：`CCCn1c(=O)c2[nH]c(C3CC4CCC(C3)C4CC(=O)O)nc2n(CCC)c1=O`
* `ord-5c76c4a7daf5438cab96058325b857ae`
  * 反应物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)O)C(=O)OCC + C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)(C(=O)OCC)C(=O)OCC`
  * 生成命中：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
  * 记录产物：`C=CCOC(=O)NC(Cc1cc(C2CCCN2C(=O)OC(C)(C)C)no1)C(=O)OCC`
* `ord-5573c3af085c4ad39e195fab14b73779`
  * 反应物：`O + O=C(O)C(CC1=Cc2ccccc21)C(=O)O`
  * 生成命中：`O=C(O)CCC1=Cc2ccccc21`
  * 记录产物：`O=C(O)CCC1=Cc2ccccc21`

### `elimination_deamination_001` 氧化脱氨成羰基

* `ord-2f581446dccc4df89ac08939b0a8b4ad`
  * 反应物：`CC(C)(C)OC(=O)N[C@H](CCCNC(=N)N[N+](=O)[O-])C(=O)O + CCN(CC)CC + CN(C)C(On1nnc2ccccc21)=[N+](C)C.F[B-](F)(F)F + Cl.NCCc1ccc(O)cc1`
  * 生成命中：`N`
  * 记录产物：`CC(C)(C)OC(=O)NC(CCCNC(N)=N[N+](=O)[O-])C(=O)NCCc1ccc(O)cc1 ; N`
* `ord-fc70462efd6c45659e9169b8717b2d49`
  * 反应物：`C1N2CN3CN1CN(C2)C3 + CC(C)(C)c1cc(CN)c(O)c(S(C)(=O)=O)c1.Cl + Cl + O=C(O)C(F)(F)F`
  * 生成命中：`CC(C)(C)c1cc(C=O)c(O)c(S(C)(=O)=O)c1`
  * 记录产物：`CC(C)(C)c1cc(C=O)c(O)c(S(C)(=O)=O)c1`
* `ord-e2471430116d4b988ea6326d8d16cab5`
  * 反应物：`COC(=O)C(F)F + ClCCl + NCCO`
  * 生成命中：`N`
  * 记录产物：`N ; O=C(NCCO)C(F)F`

### `esterification_transesterification_001` 酯交换

* `ord-23a5242235f843fa9d331c47debf3305`
  * 反应物：`C=COC(C)=O + CCN(CC)CC + ClC(Cl)Cl + O[C@@H]1C=C[C@H](OC2CCCCO2)C1`
  * 生成命中：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
  * 记录产物：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
* `ord-b1d02d975dd644069dccecc38e8a3752`
  * 反应物：`CC(=O)O + CC(=O)OC[C@H]1CN(c2cc(F)c(C3=CCN(C(=O)[C@@H]4COC(C)(C)O4)CC3)c(F)c2)C(=O)O1 + O=C([O-])O.[Na+] + O=C([O-])[O-].[K+].[K+]`
  * 生成命中：`CC1(C)OCC(C(=O)N2CC=C(c3c(F)cc(N4CC(CO)OC4=O)cc3F)CC2)O1`
  * 记录产物：`CC1(C)OCC(C(=O)N2CC=C(c3c(F)cc(N4CC(CO)OC4=O)cc3F)CC2)O1`
* `ord-c79eca467f9347519f110d1079b2558d`
  * 反应物：`C1CCOC1 + CO + C[C@@H](OC(=O)c1ccc([N+](=O)[O-])cc1)[C@H](NC(=O)OC(C)(C)C)c1cc(F)c(F)c(F)c1 + O=C([O-])[O-].[K+].[K+]`
  * 生成命中：`CC(O)C(NC(=O)OC(C)(C)C)c1cc(F)c(F)c(F)c1`
  * 记录产物：`CC(O)C(NC(=O)OC(C)(C)C)c1cc(F)c(F)c(F)c1`

### `esterification_intermolecular_001` 酯化(分子间)

* `ord-aefa3b74c30b479da2d952052a0e8df6`
  * 反应物：`CO + O=C(O)CCc1cnc(-c2cccc(C(=O)O)c2)o1 + O=S(Cl)Cl`
  * 生成命中：`COC(=O)CCc1cnc(-c2cccc(C(=O)O)c2)o1`
  * 记录产物：`COC(=O)CCc1cnc(-c2cccc(C(=O)O)c2)o1`
* `ord-f9f37bcdc3464a7d9848ba524564d05b`
  * 反应物：`C/C(=C\C(=O)OCCCCCCCCC(=O)O)C[C@@H]1OC[C@H](C[C@@H]2O[C@H]2[C@@H](C)[C@H](C)O)[C@@H](O)[C@H]1O + CCCCC(CC)C(=O)[O-].[Ca]`
  * 生成命中：`O`
  * 记录产物：`CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O ; CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O.CC(=CC(=O)OCCCCCCCCC(=O)[O-])CC1OCC(CC2OC2C(C)C(C)O)C(O)C1O.O.O.[Ca+2] ; O ; [Ca+2]`
* `ord-dabb0134a3664218ab80ff869d75d7fc`
  * 反应物：`CC(CC(=O)O)c1ccccc1 + CO + O=S(Cl)Cl`
  * 生成命中：`COC(=O)CC(C)c1ccccc1`
  * 记录产物：`COC(=O)CC(C)c1ccccc1`

### `condensation_schiff_base_001` 席夫碱生成

* `ord-ad367c0052f942b5b42ca2f28c63efc1`
  * 反应物：`Nc1ccc(Cl)c(Cl)c1 + O=Cc1ccccc1`
  * 生成命中：`Clc1ccc(N=Cc2ccccc2)cc1Cl`
  * 记录产物：`Clc1ccc(N=Cc2ccccc2)cc1Cl`
* `ord-895a158fa06c484e8752e20e0f54962f`
  * 反应物：`Cc1ccccc1 + Cl.NCCCC[C@H](N)C(=O)O + O=Cc1ccccc1`
  * 生成命中：`NC(CCCCN=Cc1ccccc1)C(=O)O`
  * 记录产物：`NC(CCCCN=Cc1ccccc1)C(=O)O`
* `ord-4c1a66e4a85044c985a27efcecdb09d2`
  * 反应物：`CC(C)(C)C=O + NC1CCNC1`
  * 生成命中：`CC(C)(C)C=NC1CCNC1`
  * 记录产物：`CC(C)(C)C=NC1CCNC1`

### `amidation_intermolecular_001` 酰胺化(分子间)

* `ord-6484a284b0aa46eaae0c0af132625719`
  * 反应物：`C[C@](O)(C(=O)O)C(F)(F)F + Nc1cccc2c1C(=O)c1sccc1CO2`
  * 生成命中：`CC(O)(C(=O)Nc1cccc2c1C(=O)c1sccc1CO2)C(F)(F)F`
  * 记录产物：`CC(O)(C(=O)Nc1cccc2c1C(=O)c1sccc1CO2)C(F)(F)F`
* `ord-a50f7cac2645481a8747ad859fb15edc`
  * 反应物：`CC(C)(CC(=O)O)NC(=O)OC(C)(C)C + CCN(CC)CC + CN(C)[P+](On1nnc2ccccc21)(N(C)C)N(C)C.F[P-](F)(F)(F)(F)F + N[C@H](CCc1ccccc1)C(=O)OCc1ccccc1`
  * 生成命中：`CC(C)(CC(=O)NC(CCc1ccccc1)C(=O)OCc1ccccc1)NC(=O)OC(C)(C)C`
  * 记录产物：`CC(C)(CC(=O)NC(CCc1ccccc1)C(=O)OCc1ccccc1)NC(=O)OC(C)(C)C`
* `ord-ac9b042f4b28460bbb5f5ac06fb31c97`
  * 反应物：`COc1ccc(N)cc1 + N#Cc1ccc(C(=O)O)cc1`
  * 生成命中：`COc1ccc(NC(=O)c2ccc(C#N)cc2)cc1`
  * 记录产物：`COc1ccc(NC(=O)c2ccc(C#N)cc2)cc1`

### `aminolysis_ester_001` 酯的氨解

* `ord-2e03a241be2b4b53bf88ccfacb21967f`
  * 反应物：`CC(=O)Cl + CCN(CC)CC + CCOC(C)=O + Nc1ccc(Cl)cc1F`
  * 生成命中：`CC(=O)Nc1ccc(Cl)cc1F`
  * 记录产物：`CC(=O)Nc1ccc(Cl)cc1F`
* `ord-55df25e97ace40dfac201fefc1def505`
  * 反应物：`CC(=O)OC(C)=O + Cc1ccc(N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)C(=O)c2ccc(N)cc2)cc1`
  * 生成命中：`CC(=O)Nc1ccc(C(=O)N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)c2ccc(C)cc2)cc1`
  * 记录产物：`CC(=O)Nc1ccc(C(=O)N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)c2ccc(C)cc2)cc1`
* `ord-a37d4b3af3174cb3b9d2b4d6eb76f09a`
  * 反应物：`CC(=O)NC1(c2ccccc2)CCN(C(Cc2cc(C(F)(F)F)cc(C(F)(F)F)c2)CC(CN)c2ccc(Cl)c(Cl)c2)CC1 + CC(=O)OC(C)=O + CCN(C(C)C)C(C)C`
  * 生成命中：`CC(=O)NCC(CC(Cc1cc(C(F)(F)F)cc(C(F)(F)F)c1)N1CCC(NC(C)=O)(c2ccccc2)CC1)c1ccc(Cl)c(Cl)c1`
  * 记录产物：`CC(=O)NCC(CC(Cc1cc(C(F)(F)F)cc(C(F)(F)F)c1)N1CCC(NC(C)=O)(c2ccccc2)CC1)c1ccc(Cl)c(Cl)c1`

### `condensation_glycosylation_001` 糖苷化

* `ord-00fd638c0d41464696bea49aa4c5a664`
  * 反应物：`CO + OC[C@H]1O[C@H](O)[C@H](O)[C@@H](O)[C@@H]1O`
  * 生成命中：`COC1OC(CO)C(O)C(O)C1O`
  * 记录产物：`COC1OC(CO)C(O)C(O)C1O`

### `addition_michael_thiol_001` Michael加成(硫醇)

* `ord-beff670127204f91a07e6837e3ee54fa`
  * 反应物：`C=CC(=O)OC + SCc1cccs1`
  * 生成命中：`COC(=O)CCSCc1cccs1`
  * 记录产物：`COC(=O)CCSCc1cccs1`
* `ord-9ee6b332fc8a4354a5af6400afddf0d7`
  * 反应物：`C=CC(=O)OCC + CCN(CC)CC + Sc1ccc(Br)cc1 + [Na+].[OH-]`
  * 生成命中：`CCOC(=O)CCSc1ccc(Br)cc1`
  * 记录产物：`CCOC(=O)CCSc1ccc(Br)cc1`
* `ord-4ad75fdc2be94c2e9ba4760d1b2a1334`
  * 反应物：`C=C(C)C(=O)O + COc1ccc(CS)cc1 + [Na+].[OH-]`
  * 生成命中：`COc1ccc(CSCC(C)C(=O)O)cc1`
  * 记录产物：`COc1ccc(CSCC(C)C(=O)O)cc1`

### `addition_michael_amine_001` Michael加成(胺)

* `ord-37bf6db4682043d784aacf127e737472`
  * 反应物：`CC(=O)C=C=O + Nc1ccc(N2CCOCC2)c(Cl)c1`
  * 生成命中：`CC(=O)CC(=O)Nc1ccc(N2CCOCC2)c(Cl)c1`
  * 记录产物：`CC(=O)CC(=O)Nc1ccc(N2CCOCC2)c(Cl)c1`
* `ord-0b93aa94662c4e62b1e0a9feeacf9e77`
  * 反应物：`C=CC(N)=O + COc1c(N2CC(C)NC(C)C2)c(F)cc2c(=O)c(C(=O)NCc3ccc(OC(F)(F)F)cc3C)cn(CC(F)(F)F)c12 + [Li+].[O-][Cl+3]([O-])([O-])[O-]`
  * 生成命中：`COc1c(N2CC(C)N(CCC(N)=O)C(C)C2)c(F)cc2c(=O)c(C(=O)NCc3ccc(OC(F)(F)F)cc3C)cn(CC(F)(F)F)c12`
  * 记录产物：`COc1c(N2CC(C)N(CCC(N)=O)C(C)C2)c(F)cc2c(=O)c(C(=O)NCc3ccc(OC(F)(F)F)cc3C)cn(CC(F)(F)F)c12`
* `ord-5a7d51e4e8f140e2a4d91f043986827c`
  * 反应物：`CCN(CC)CC + CNCCCl.Cl + O=C1C=CC(=O)N1Cc1ccccc1`
  * 生成命中：`CN(CCCl)C1CC(=O)N(Cc2ccccc2)C1=O`
  * 记录产物：`CN(CCCl)C1CC(=O)N(Cc2ccccc2)C1=O`

### `condensation_aldol_001` 醇醛缩合(分子间)

* `ord-b89820f3efd14138aa3a6cb136df92cc`
  * 反应物：`CC(C)NC(C)C.[Li] + CCC=O + COC1(C(C)=O)CCN(C(=O)OC(C)(C)C)CC1 + [Cl-].[NH4+]`
  * 生成命中：`CCC(O)CC(=O)C1(OC)CCN(C(=O)OC(C)(C)C)CC1`
  * 记录产物：`CCC(O)CC(=O)C1(OC)CCN(C(=O)OC(C)(C)C)CC1`
* `ord-01aaf177b4544f90898b7f97d17205e5`
  * 反应物：`CCCC(=O)Cc1ccc(OCc2ccccc2)cc1 + CCOC(=O)C=O`
  * 生成命中：`CCCC(=O)C(c1ccc(OCc2ccccc2)cc1)C(O)C(=O)OCC`
  * 记录产物：`CCCC(=O)C(c1ccc(OCc2ccccc2)cc1)C(O)C(=O)OCC`
* `ord-3f0e28688d4b4c4080e09a7a0e3f0c89`
  * 反应物：`CCCCC(=O)Cc1ccc(OC2CCCCC2)c(Br)c1 + CCOC(=O)C=O`
  * 生成命中：`CCCCC(=O)C(c1ccc(OC2CCCCC2)c(Br)c1)C(O)C(=O)OCC`
  * 记录产物：`CCCCC(=O)C(c1ccc(OC2CCCCC2)c(Br)c1)C(O)C(=O)OCC`

### `elimination_amide_to_nitrile_001` 酰胺脱水成腈

* `ord-72e7e9fd9d714797ab3b1ceb025540aa`
  * 反应物：`COCCCc1nnc(-c2ccc(-c3ccccc3)nc2)n1-c1cccc(C(N)=O)c1C + O=P(Cl)(Cl)Cl`
  * 生成命中：`COCCCc1nnc(-c2ccc(-c3ccccc3)nc2)n1-c1cccc(C#N)c1C`
  * 记录产物：`COCCCc1nnc(-c2ccc(-c3ccccc3)nc2)n1-c1cccc(C#N)c1C`
* `ord-1cc20313a10549d48e76ba2b7f716b52`
  * 反应物：`CC(C)(C)OC(=O)NC1(C(=O)N[C@@H](Cc2ccc(-c3ccc(C#N)cc3)cc2)C(N)=O)CCOCC1 + CC[N+](CC)(CC)S(=O)(=O)N=C([O-])OC`
  * 生成命中：`CC(C)(C)OC(=O)NC1(C(=O)NC(C#N)Cc2ccc(-c3ccc(C#N)cc3)cc2)CCOCC1`
  * 记录产物：`CC(C)(C)OC(=O)NC1(C(=O)NC(C#N)Cc2ccc(-c3ccc(C#N)cc3)cc2)CCOCC1`
* `ord-3905e3a0cd8e42cb9715ebae1e6d24d1`
  * 反应物：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC(N)=O)CO3)cc1 + O + O=C(OC(=O)C(F)(F)F)C(F)(F)F + c1ccncc1`
  * 生成命中：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC#N)CO3)cc1`
  * 记录产物：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC#N)CO3)cc1`

### `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜

* `ord-5505b5e667d847a0be6fa845705d47a2`
  * 反应物：`CCCCCCCCS(=O)c1ccc(CC(COC(C)=O)(COC(C)=O)NC(C)=O)cc1 + O=C(OO)c1cccc(Cl)c1 + [Ca+2].[OH-].[OH-]`
  * 生成命中：`CCCCCCCCS(=O)(=O)c1ccc(CC(COC(C)=O)(COC(C)=O)NC(C)=O)cc1`
  * 记录产物：`CCCCCCCCS(=O)(=O)c1ccc(CC(COC(C)=O)(COC(C)=O)NC(C)=O)cc1`
* `ord-903333aae592446eb962b5ca72d7da12`
  * 反应物：`O=c1ccc2cc(OCCCCS(=O)c3ccc([N+](=O)[O-])cc3)ccc2[nH]1 + OO`
  * 生成命中：`O=c1ccc2cc(OCCCCS(=O)(=O)c3ccc([N+](=O)[O-])cc3)ccc2[nH]1`
  * 记录产物：`O=c1ccc2cc(OCCCCS(=O)(=O)c3ccc([N+](=O)[O-])cc3)ccc2[nH]1`
* `ord-fdc3de97a5b9453ab670189a6b0fcf03`
  * 反应物：`CCC1(C)CC(S(=O)Cc2c(F)cccc2F)=NO1 + O + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CCC1(C)CC(S(=O)(=O)Cc2c(F)cccc2F)=NO1`
  * 记录产物：`CCC1(C)CC(S(=O)(=O)Cc2c(F)cccc2F)=NO1`

### `reduction_sulfoxide_001` 亚砜还原成硫醚

* `ord-40453b2cc8d74902b8ebe4e9a37f2d13`
  * 反应物：`CS(=O)c1ccc(CCl)cc1 + CS(=O)c1ccc(C[P+](c2ccccc2)(c2ccccc2)c2ccccc2)cc1.[Cl-]`
  * 生成命中：`CSc1ccc(C[P+](c2ccccc2)(c2ccccc2)c2ccccc2)cc1`
  * 记录产物：`CSc1ccc(C[P+](c2ccccc2)(c2ccccc2)c2ccccc2)cc1 ; CSc1ccc(C[P+](c2ccccc2)(c2ccccc2)c2ccccc2)cc1.[Cl-] ; [Cl-]`
* `ord-989a0e61f7dd456491b195740e3faab1`
  * 反应物：`CCOC(C)=O + O=C(O)c1ccc(Cl)c2c1NCCS2=O`
  * 生成命中：`O=C(O)c1ccc(Cl)c2c1NCCS2`
  * 记录产物：`O=C(O)c1ccc(Cl)c2c1NCCS2`
* `ord-6f94b5032af64c718c3e642091a45142`
  * 反应物：`CC(=O)Cl + CCON=CC1=C(C(=O)O)N2C(=O)C(NC(=O)Cc3cccs3)[C@H]2S(=O)C1`
  * 生成命中：`CCON=CC1=C(C(=O)O)N2C(=O)C(NC(=O)Cc3cccs3)C2SC1`
  * 记录产物：`CCON=CC1=C(C(=O)O)N2C(=O)C(NC(=O)Cc3cccs3)C2SC1`

### `oxidation_diphenol_para_001` 对二酚氧化成醌

* `ord-76b77f0e77ff4e818e609c821b2df0a5`
  * 反应物：`O=C(c1ccccc1)c1c(-c2ccccc2)c(O)c2ccccc2c1O`
  * 生成命中：`O=C(C1=C(c2ccccc2)C(=O)c2ccccc2C1=O)c1ccccc1`
  * 记录产物：`O=C(C1=C(c2ccccc2)C(=O)c2ccccc2C1=O)c1ccccc1`

### `reduction_quinone_para_001` 对醌还原成二酚

* `ord-ea2aaea7fcb84ecf97673d17fa69c1c4`
  * 反应物：`CO + O=C1C=C(Cl)C(=O)C2C1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
  * 生成命中：`Oc1cc(Cl)c(O)c2c1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
  * 记录产物：`Oc1cc(Cl)c(O)c2c1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
* `ord-d264a4b8ce364c998253ee55ac74f6a8`
  * 反应物：`CCN(C(C)C)C(C)C + COC1=CC(=O)C=C(OC)C1=O + O + O=C(O)CCS`
  * 生成命中：`COc1cc(O)cc(OC)c1O`
  * 记录产物：`COc1cc(O)cc(OC)c1O ; COc1cc(O)cc(OC)c1O.O=C(O)CCS ; O=C(O)CCS`
* `ord-03e017359bef41e5810a67213f91c3bd`
  * 反应物：`C + CC1=C(C)C(=O)C(CC[C@](C)(O)CO)=C(C)C1=O + [H][H]`
  * 生成命中：`Cc1c(C)c(O)c(CCC(C)(O)CO)c(C)c1O`
  * 记录产物：`Cc1c(C)c(O)c(CCC(C)(O)CO)c(C)c1O`

## 失败/无命中说明

* 没有 `product_match` 的规则不等于“规则错”：可能是 ORD 抽样里没有该反应类型、底物取代基不匹配、规则要求多步/共试剂，或记录方向相反。
* `run_errors` 是 RDKit 在具体底物上抛错的次数，已逐条累计；`invalid_products` 是生成物无法规范化的次数。
* 需要外部权威规则来源时，下一步应查论文/数据集原文；本报告只回答“有没有在 ORD 真实记录里跑出相同产物”。
