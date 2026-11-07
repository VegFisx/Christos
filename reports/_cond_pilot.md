# 第七十五轮 · 规则来源体检（ORD 真实反应实测）

> **做法**：把每条规则的 SMARTS 套到 ORD 真实记录的**反应物**上，生成产物经「去映射号 / 去显式 H / 去立体 / 拆片段」规范化，再与记录的真实产物比对。
> **product_match** = 生成片段与该记录真实产物有交集；**fired** = 规则至少生成过一个可解析产物。

## 口径（先看这段）

* 数据源：`D:\ProgramData\DSHNS\chemreact-staging\data\ord_reaction_index.jsonl`，共 1,770,980 行；按步长 885 等距抽样，实际扫描 **2,000** 条。
* 这是**前向试跑**，不是逆合成审计；ORD 记录未必是同一反应类型，所以 `fired` 多不代表规则对，只代表底物里存在可匹配子结构。
* 规则里的水/共试剂多为**隐含**（如水解规则不把 H2O 写成反应物），因此本审计只把规则套到记录的反应物列；这比方案 a 的模板签名更接近真实用法。
* 规范化忽略立体与显式 H；`product_match` 是**分子图相同**，不是条件/机理相同。
* 只给计数与样例，**不打分、不排序**；`rules.json` 原顺序。

## 总览

* 规则：**64** 条（{'论文修正': 11, '论文原样': 11, '自写新增': 42}）
* 至少 `fired` 一次：**59** 条
* 至少 `product_match` 一次：**29** 条
* 反应物解析失败：**0** 次；产物解析失败：**0** 次

### 条件覆盖（所有 product_match 记录）

| 规则 | 命中记录 | 温度 | 催化剂 | 溶剂 | 试剂 | 任一条件 |
|---|---:|---:|---:|---:|---:|---:|
| `hydrolysis_ester_001` 酯水解 | 55 | 11 | 1 | 50 | 0 | 50 |
| `hydrolysis_amide_001` 酰胺水解 | 49 | 8 | 10 | 46 | 0 | 47 |
| `hydrolysis_acetal_001` 缩醛水解 | 2 | 0 | 0 | 2 | 0 | 2 |
| `oxidation_hydroxyl_001` 羟基氧化 | 7 | 1 | 2 | 6 | 0 | 6 |
| `oxidation_aldehyde_001` 醛氧化 | 3 | 1 | 1 | 3 | 0 | 3 |
| `oxidation_amine_001` 胺氧化 | 1 | 0 | 0 | 0 | 0 | 0 |
| `reduction_ketone_001` 酮还原 | 16 | 3 | 2 | 13 | 0 | 14 |
| `elimination_dehydration_001` 脱水 | 4 | 0 | 2 | 4 | 0 | 4 |
| `demethylation_aromatic_001` 脱甲基 | 8 | 4 | 0 | 6 | 0 | 7 |
| `decarboxylation_aromatic_001` 芳香酸脱羧 | 1 | 0 | 1 | 1 | 0 | 1 |
| `hydration_alkene_001` 烯烃水合 | 2 | 1 | 0 | 2 | 0 | 2 |
| `oxidation_primary_alcohol_001` 伯醇氧化成醛 | 8 | 2 | 3 | 8 | 0 | 8 |
| `oxidation_sulfide_001` 硫醚氧化成亚砜 | 7 | 1 | 1 | 6 | 0 | 6 |
| `oxidation_epoxide_001` 双键环氧化 | 1 | 1 | 0 | 1 | 0 | 1 |
| `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基 | 2 | 1 | 0 | 2 | 0 | 2 |
| `reduction_aldehyde_001` 醛还原成醇 | 9 | 2 | 1 | 8 | 0 | 8 |
| `reduction_alkene_001` 双键加氢 | 13 | 0 | 11 | 13 | 0 | 13 |
| `reduction_nitro_001` 硝基还原成胺 | 40 | 4 | 29 | 36 | 0 | 36 |
| `hydrolysis_lactam_001` 内酰胺开环 | 37 | 5 | 8 | 35 | 0 | 35 |
| `hydrolysis_imine_001` 亚胺水解 | 1 | 0 | 0 | 1 | 0 | 1 |
| `isomerization_epimerization_001` 差向异构化 | 6 | 1 | 0 | 3 | 0 | 3 |
| `elimination_deamination_001` 氧化脱氨成羰基 | 1 | 0 | 0 | 0 | 0 | 0 |
| `esterification_transesterification_001` 酯交换 | 6 | 5 | 3 | 5 | 0 | 6 |
| `esterification_intermolecular_001` 酯化(分子间) | 25 | 5 | 4 | 13 | 0 | 17 |
| `condensation_schiff_base_001` 席夫碱生成 | 1 | 0 | 0 | 1 | 0 | 1 |
| `amidation_intermolecular_001` 酰胺化(分子间) | 104 | 11 | 7 | 72 | 0 | 73 |
| `aminolysis_ester_001` 酯的氨解 | 24 | 4 | 0 | 17 | 0 | 17 |
| `condensation_aldol_001` 醇醛缩合(分子间) | 1 | 0 | 0 | 1 | 0 | 1 |
| `elimination_amide_to_nitrile_001` 酰胺脱水成腈 | 1 | 0 | 0 | 1 | 0 | 1 |

## 逐条结果

| # | 规则 | 类别 | 状态 | 论文档位 | fired | product_match | run_errors | 首个命中 rid |
|---|---|---|---|---|---|---|---|---|
| 1 | `hydrolysis_ester_001` 酯水解 | hydrolysis | active | 论文修正 | 741 | 55 | 0 | ord-92a035dfa8074c4da7438e5bc4590d3a |
| 2 | `hydrolysis_glycoside_001` 糖苷水解 | hydrolysis | active | 论文修正 | 7 | 0 | 0 | — |
| 3 | `hydrolysis_amide_001` 酰胺水解 | hydrolysis | active | 论文修正 | 659 | 49 | 0 | ord-3f15bf221dc54fad9271a09bdff7e39f |
| 4 | `hydrolysis_sulfate_001` 硫酸酯水解 | hydrolysis | active | 论文原样 | 19 | 0 | 0 | — |
| 5 | `hydrolysis_phosphate_001` 磷酸酯水解 | hydrolysis | active | 论文原样 | 10 | 0 | 0 | — |
| 6 | `hydrolysis_acetal_001` 缩醛水解 | hydrolysis | active | 论文修正 | 32 | 2 | 0 | ord-847105c1692d455080369114984b6d46 |
| 7 | `hydrolysis_hemiacetal_001` 半缩醛水解 | hydrolysis | active | 论文原样 | 1 | 0 | 0 | — |
| 8 | `oxidation_hydroxyl_001` 羟基氧化 | oxidation | active | 论文原样 | 134 | 7 | 0 | ord-434e3e2fb22e43b082074d31980f300e |
| 9 | `oxidation_aldehyde_001` 醛氧化 | oxidation | active | 论文原样 | 190 | 3 | 0 | ord-dddae2411ad44dc9ba975eaf6c427c28 |
| 10 | `oxidation_phenol_quinone_001` 酚氧化成醌 | oxidation | active | 论文原样 | 3 | 0 | 0 | — |
| 11 | `oxidation_amine_001` 胺氧化 | oxidation | active | 论文修正 | 102 | 1 | 0 | ord-880ac37b3955411491cae66a6889f58c |
| 12 | `reduction_ketone_001` 酮还原 | reduction | active | 论文原样 | 1357 | 16 | 0 | ord-75ae478bd80e476b9173572378913963 |
| 13 | `reduction_quinone_001` 醌还原 | reduction | active | 论文修正 | 8 | 0 | 0 | — |
| 14 | `elimination_dehydration_001` 脱水 | elimination | active | 论文修正 | 272 | 4 | 0 | ord-6ef1df6c7c9b4e45906873947a66c6ee |
| 15 | `demethylation_aromatic_001` 脱甲基 | demethylation | active | 论文修正 | 252 | 8 | 0 | ord-e2821df72e58476aa0b04fe1814b77ab |
| 16 | `decarboxylation_aromatic_001` 芳香酸脱羧 | decarboxylation | active | 论文原样 | 131 | 1 | 0 | ord-2447bbbad4af4dbdb4ec6e34b3d8a503 |
| 17 | `decarboxylation_beta_keto_001` β-酮酸脱羧 | decarboxylation | active | 论文修正 | 2 | 0 | 0 | — |
| 18 | `hydroxylation_aromatic_001` 芳香环羟基化 | hydroxylation | active | 论文原样 | 1829 | 0 | 0 | — |
| 19 | `hydration_alkene_001` 烯烃水合 | hydration | active | 论文原样 | 244 | 2 | 0 | ord-167aa8ae8ea442419175105f9aef78c4 |
| 20 | `hydration_enone_001` α,β-不饱和羰基水合 | hydration | active | 论文修正 | 104 | 0 | 0 | — |
| 21 | `tautomerization_keto_enol_001` 酮-烯醇化 | rearrangement | active | 论文修正 | 906 | 0 | 0 | — |
| 22 | `esterification_gamma_lactone_001` γ-内酯化 | esterification | active | 自写新增 | 1 | 0 | 0 | — |
| 23 | `esterification_delta_lactone_001` δ-内酯化 | esterification | active | 自写新增 | 0 | 0 | 0 | — |
| 24 | `maillard_simplified_001` 美拉德简化 | condensation | active | 论文原样 | 3 | 0 | 0 | — |
| 25 | `oxidation_primary_alcohol_001` 伯醇氧化成醛 | oxidation | active | 自写新增 | 182 | 8 | 0 | ord-94d09087271b4328a2c67bc52eba23b2 |
| 26 | `oxidation_sulfide_001` 硫醚氧化成亚砜 | oxidation | active | 自写新增 | 174 | 7 | 0 | ord-77762fe0ea0b42919686e65eab98a63e |
| 27 | `oxidation_epoxide_001` 双键环氧化 | oxidation | active | 自写新增 | 244 | 1 | 0 | ord-5cd745230f16451da89bf64edf0df283 |
| 28 | `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基 | oxidation | active | 自写新增 | 527 | 2 | 0 | ord-e22e3fdd8818442586447102a6833261 |
| 29 | `oxidation_thiol_disulfide_001` 硫醇偶联成二硫 | oxidation | disabled | 自写新增 | 0 | 0 | 0 | — |
| 30 | `reduction_aldehyde_001` 醛还原成醇 | reduction | active | 自写新增 | 190 | 9 | 0 | ord-75ae478bd80e476b9173572378913963 |
| 31 | `reduction_alkene_001` 双键加氢 | reduction | active | 自写新增 | 244 | 13 | 0 | ord-3640c8aaa94d4416a6841f2457352d20 |
| 32 | `reduction_nitro_001` 硝基还原成胺 | reduction | disabled | 自写新增 | 173 | 40 | 0 | ord-3805bcf4ac35487b889e58f78d128e4e |
| 33 | `hydrolysis_epoxide_001` 环氧化物开环成二醇 | hydrolysis | active | 自写新增 | 13 | 0 | 0 | — |
| 34 | `hydrolysis_lactam_001` 内酰胺开环 | hydrolysis | active | 自写新增 | 457 | 37 | 0 | ord-3f15bf221dc54fad9271a09bdff7e39f |
| 35 | `hydrolysis_imine_001` 亚胺水解 | hydrolysis | active | 自写新增 | 6 | 1 | 0 | ord-e32b9968b3dc4b0aa05fbebfe7aa9b79 |
| 36 | `cyclization_hemiacetal_001` 分子内半缩醛化 | cyclization | active | 自写新增 | 1 | 0 | 0 | — |
| 37 | `cyclization_lactam_001` 分子内酰胺化 | cyclization | active | 自写新增 | 1 | 0 | 0 | — |
| 38 | `cyclization_ether_001` 分子内脱水成醚 | cyclization | active | 自写新增 | 4 | 0 | 0 | — |
| 39 | `cyclization_lactone_delta_001` δ-羟基酸内酯化(备用) | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 40 | `condensation_aldol_intra_001` 分子内羟醛缩合 | condensation | disabled | 自写新增 | 0 | 0 | 0 | — |
| 41 | `isomerization_double_bond_001` 双键位置异构 | rearrangement | active | 自写新增 | 53 | 0 | 0 | — |
| 42 | `isomerization_epimerization_001` 差向异构化 | rearrangement | disabled | 自写新增 | 117 | 6 | 0 | ord-92a446f0ee374bf5b6f980c4166659da |
| 43 | `rearrangement_retro_aldol_001` 逆羟醛裂解 | rearrangement | active | 自写新增 | 28 | 0 | 0 | — |
| 44 | `decarboxylation_malonic_001` 丙二酸型脱羧 | decarboxylation | active | 自写新增 | 2 | 0 | 0 | — |
| 45 | `elimination_deamination_001` 氧化脱氨成羰基 | elimination | active | 自写新增 | 102 | 1 | 0 | ord-880ac37b3955411491cae66a6889f58c |
| 46 | `elimination_decarboxylation_phenol_001` 酚酸脱羧成酚 | decarboxylation | disabled | 自写新增 | 2 | 0 | 0 | — |
| 47 | `esterification_transesterification_001` 酯交换 | esterification | active | 自写新增 | 249 | 6 | 0 | ord-da7d24e50de54b24b7fe7918c9ca080e |
| 48 | `esterification_intermolecular_001` 酯化(分子间) | esterification | active | 自写新增 | 460 | 25 | 0 | ord-f2832b5fb09b4e59ad1cd227ee44f57d |
| 49 | `condensation_schiff_base_001` 席夫碱生成 | condensation | active | 自写新增 | 38 | 1 | 0 | ord-696de05f6c3a4ea4b5110db9d813a8de |
| 50 | `amidation_intermolecular_001` 酰胺化(分子间) | condensation | active | 自写新增 | 311 | 104 | 0 | ord-91c62d2f07f84c8dbeb530ddca5c965b |
| 51 | `aminolysis_ester_001` 酯的氨解 | condensation | active | 自写新增 | 407 | 24 | 0 | ord-2aaa495b46bc4d9b8a75a64dde900409 |
| 52 | `condensation_glycosylation_001` 糖苷化 | condensation | active | 自写新增 | 1 | 0 | 0 | — |
| 53 | `condensation_hemiacetal_001` 半缩醛形成(分子间) | condensation | active | 自写新增 | 84 | 0 | 0 | — |
| 54 | `addition_michael_thiol_001` Michael加成(硫醇) | addition | active | 自写新增 | 1 | 0 | 0 | — |
| 55 | `addition_michael_amine_001` Michael加成(胺) | addition | active | 自写新增 | 57 | 0 | 0 | — |
| 56 | `condensation_aldol_001` 醇醛缩合(分子间) | condensation | active | 自写新增 | 906 | 1 | 0 | ord-5faf9a9442e24816b9ff9951478faafc |
| 57 | `addition_thiohemiacetal_001` 硫代半缩醛形成 | addition | active | 自写新增 | 1 | 0 | 0 | — |
| 58 | `elimination_amide_to_nitrile_001` 酰胺脱水成腈 | elimination | active | 自写新增 | 33 | 1 | 0 | ord-e9274e4c4fed4362a879e98a886da25c |
| 59 | `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜 | oxidation | active | 自写新增 | 69 | 0 | 0 | — |
| 60 | `reduction_sulfoxide_001` 亚砜还原成硫醚 | reduction | active | 自写新增 | 69 | 0 | 0 | — |
| 61 | `decarboxylation_cinnamic_001` 肉桂酸型脱羧 | decarboxylation | active | 自写新增 | 9 | 0 | 0 | — |
| 62 | `oxidation_diphenol_para_001` 对二酚氧化成醌 | oxidation | active | 自写新增 | 0 | 0 | 0 | — |
| 63 | `reduction_quinone_para_001` 对醌还原成二酚 | reduction | active | 自写新增 | 5 | 0 | 0 | — |
| 64 | `esterification_paper_original_001` 酯化(论文原版·产物模板有误) | esterification | disabled | 自写新增 | 14 | 0 | 0 | — |

## 命中样例（前 3 条）

### `hydrolysis_ester_001` 酯水解

* `ord-92a035dfa8074c4da7438e5bc4590d3a`
  * 反应物：`CCOC(=O)c1nc(C)oc1CCc1cccc(Cl)c1 + [K+].[OH-]`
  * 生成命中：`Cc1nc(C(=O)O)c(CCc2cccc(Cl)c2)o1`
  * 记录产物：`Cc1nc(C(=O)O)c(CCc2cccc(Cl)c2)o1`
* `ord-8b013eee0bdb4687817055bccfa46f38`
  * 反应物：`CC(C)(C)OC(=O)C(CNC(=O)C1(CC(=O)O)CCCC1)Cc1ccc(Cl)c(Cl)c1 + O=C(O)C(F)(F)F`
  * 生成命中：`O=C(O)CC1(C(=O)NCC(Cc2ccc(Cl)c(Cl)c2)C(=O)O)CCCC1`
  * 记录产物：`O=C(O)CC1(C(=O)NCC(Cc2ccc(Cl)c(Cl)c2)C(=O)O)CCCC1`
* `ord-634675a8015b4666968d8cdd5cb40b3f`
  * 反应物：`CC(Oc1ccc(CNC(=O)c2cccnc2Oc2ccc3nonc3c2)c(F)c1)C(=O)OC(C)(C)C`
  * 生成命中：`CC(Oc1ccc(CNC(=O)c2cccnc2Oc2ccc3nonc3c2)c(F)c1)C(=O)O`
  * 记录产物：`CC(Oc1ccc(CNC(=O)c2cccnc2Oc2ccc3nonc3c2)c(F)c1)C(=O)O`

### `hydrolysis_amide_001` 酰胺水解

* `ord-3f15bf221dc54fad9271a09bdff7e39f`
  * 反应物：`C=CCOC(=O)N(Cc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1)C(C)(C)C + CCN(C(C)C)C(C)C`
  * 生成命中：`CC(C)(C)NCc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1`
  * 记录产物：`CC(C)(C)NCc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1`
* `ord-6fd8d293355045979e6505dd8785f092`
  * 反应物：`O=C(OCc1ccccc1)N1CCC(N2CCCCCC2=O)CC1`
  * 生成命中：`O=C1CCCCCN1C1CCNCC1`
  * 记录产物：`O=C1CCCCCN1C1CCNCC1`
* `ord-293c5493b0564c5dbb41fd0b42172a02`
  * 反应物：`C=CC(Cl)=C(Cl)Cl + CC(C)C(=O)N(C)C + CCN(CC)CC + O`
  * 生成命中：`CNC`
  * 记录产物：`C=CC(Cl)=C(Cl)Cl ; CNC`

### `hydrolysis_acetal_001` 缩醛水解

* `ord-847105c1692d455080369114984b6d46`
  * 反应物：`CCCCCC#CCC#C/C=C/COC(C)OCC + O=S(=O)(O)O`
  * 生成命中：`CCCCCC#CCC#CC=CCO`
  * 记录产物：`CCCCCC#CCC#CC=CCO`
* `ord-76cf567b92a14cd383b37898a4eeaa7f`
  * 反应物：`C=C(F)CN(CC(OC)OC)C(=O)OCC + O=CO + [Cl-].[Na+]`
  * 生成命中：`C=C(F)CN(CC=O)C(=O)OCC`
  * 记录产物：`C=C(F)CN(CC=O)C(=O)OCC`

### `oxidation_hydroxyl_001` 羟基氧化

* `ord-434e3e2fb22e43b082074d31980f300e`
  * 反应物：`CS(=O)(=O)CC(O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl + O.O.O.O.O.O=S([O-])([O-])=S.[Na+].[Na+] + O=C([O-])O.[Na+]`
  * 生成命中：`CS(=O)(=O)CC(=O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl`
  * 记录产物：`CS(=O)(=O)CC(=O)c1cc2[nH]cnc2c(F)c1Nc1ccc(Br)cc1Cl`
* `ord-fda79df731ff474fa2c784e0d57f7c6a`
  * 反应物：`CC#N + Cn1cncc1C(O)c1ccc(C#N)c(F)c1`
  * 生成命中：`Cn1cncc1C(=O)c1ccc(C#N)c(F)c1`
  * 记录产物：`Cn1cncc1C(=O)c1ccc(C#N)c(F)c1`
* `ord-000b3c39fb8043d2a150d9df44ebb1db`
  * 反应物：`CCC(O)c1c(C)c(NC(=O)CC(C)(C)C)c(C)c2c1OCC2c1ccc(C(C)C)cc1`
  * 生成命中：`CCC(=O)c1c(C)c(NC(=O)CC(C)(C)C)c(C)c2c1OCC2c1ccc(C(C)C)cc1`
  * 记录产物：`CCC(=O)c1c(C)c(NC(=O)CC(C)(C)C)c(C)c2c1OCC2c1ccc(C(C)C)cc1`

### `oxidation_aldehyde_001` 醛氧化

* `ord-dddae2411ad44dc9ba975eaf6c427c28`
  * 反应物：`C[Si](C)(C)CCOCn1cc(C=O)c2nc(-c3nn(CC(=O)N4CCOCC4)c4cc(F)ccc34)cnc21 + NS(=O)(=O)O + O=P([O-])(O)O.[K+] + [Na+].[O-][Cl+][O-]`
  * 生成命中：`C[Si](C)(C)CCOCn1cc(C(=O)O)c2nc(-c3nn(CC(=O)N4CCOCC4)c4cc(F)ccc34)cnc21`
  * 记录产物：`C[Si](C)(C)CCOCn1cc(C(=O)O)c2nc(-c3nn(CC(=O)N4CCOCC4)c4cc(F)ccc34)cnc21`
* `ord-7fad09f4f2dd4d05b8de5c4b12789def`
  * 反应物：`Cc1c(C=O)ccc2c1OCCO2 + O=S([O-])[O-].[Na+].[Na+] + [Na+].[OH-]`
  * 生成命中：`Cc1c(C(=O)O)ccc2c1OCCO2`
  * 记录产物：`Cc1c(C(=O)O)ccc2c1OCCO2`
* `ord-86d4cae0c6ae4001baedc53d507ef9d9`
  * 反应物：`O=Cc1cnc2cc(F)ccc2n1 + OO`
  * 生成命中：`O=C(O)c1cnc2cc(F)ccc2n1`
  * 记录产物：`O=C(O)c1cnc2cc(F)ccc2n1`

### `oxidation_amine_001` 胺氧化

* `ord-880ac37b3955411491cae66a6889f58c`
  * 反应物：`NCc1ccccc1 + O=c1ccc2c([C@@H]3CO3)ccc(OCc3ccccc3)c2[nH]1`
  * 生成命中：`N`
  * 记录产物：`N ; O=c1ccc2c(C(O)CNCc3ccccc3)ccc(OCc3ccccc3)c2[nH]1`

### `reduction_ketone_001` 酮还原

* `ord-75ae478bd80e476b9173572378913963`
  * 反应物：`COC(=O)[C@H](Cc1ccc(-c2ccccc2C=O)cc1)NC(=O)c1c(Cl)cccc1Cl + [BH4-].[Na+]`
  * 生成命中：`COC(=O)C(Cc1ccc(-c2ccccc2CO)cc1)NC(=O)c1c(Cl)cccc1Cl`
  * 记录产物：`COC(=O)C(Cc1ccc(-c2ccccc2CO)cc1)NC(=O)c1c(Cl)cccc1Cl`
* `ord-f25060e5892a4a5685309d8d781f06dc`
  * 反应物：`O=C1CC(NC(=O)C(F)(F)F)(c2ccc(-c3nc4ccn5c(-c6ncccn6)nnc5c4cc3-c3ccccc3)cc2)C1 + [BH4-].[Na+]`
  * 生成命中：`O=C(NC1(c2ccc(-c3nc4ccn5c(-c6ncccn6)nnc5c4cc3-c3ccccc3)cc2)CC(O)C1)C(F)(F)F`
  * 记录产物：`O=C(NC1(c2ccc(-c3nc4ccn5c(-c6ncccn6)nnc5c4cc3-c3ccccc3)cc2)CC(O)C1)C(F)(F)F`
* `ord-0f10161963fa4a84b4ad77b347531a06`
  * 反应物：`O=C1c2ccccc2C(=O)N1CCCOc1ccncc1 + [BH4-].[Na+]`
  * 生成命中：`O=C1c2ccccc2C(O)N1CCCOc1ccncc1`
  * 记录产物：`O=C1c2ccccc2C(O)N1CCCOc1ccncc1`

### `elimination_dehydration_001` 脱水

* `ord-6ef1df6c7c9b4e45906873947a66c6ee`
  * 反应物：`CO + CON=C(C(=O)CBr)C(=O)NC1C(=O)N2C(C(=O)O)C(O)CS[C@H]12 + O=C(OC(=O)C(F)(F)F)C(F)(F)F`
  * 生成命中：`CON=C(C(=O)CBr)C(=O)NC1C(=O)N2C(C(=O)O)=CCSC12`
  * 记录产物：`CON=C(C(=O)CBr)C(=O)NC1C(=O)N2C(C(=O)O)=CCSC12`
* `ord-6489ad2aef9c4eb98cdb21e16d3945ac`
  * 反应物：`COC(=O)Cn1nc(-c2ccc(Cl)cc2)n(C[C@@H](O)C(F)(F)F)c1=O + O=S(=O)(OS(=O)(=O)C(F)(F)F)C(F)(F)F`
  * 生成命中：`COC(=O)Cn1nc(-c2ccc(Cl)cc2)n(C=CC(F)(F)F)c1=O`
  * 记录产物：`COC(=O)Cn1nc(-c2ccc(Cl)cc2)n(C=CC(F)(F)F)c1=O`
* `ord-ed97e9e2e7c24e29abaa6979fde96075`
  * 反应物：`OC1CCc2cc3ccccc3cc21`
  * 生成命中：`C1=Cc2cc3ccccc3cc2C1`
  * 记录产物：`C1=Cc2cc3ccccc3cc2C1`

### `demethylation_aromatic_001` 脱甲基

* `ord-e2821df72e58476aa0b04fe1814b77ab`
  * 反应物：`BrB(Br)Br + CCc1cc2c(cc(OC)c(=O)n2Cc2ccc(-c3ccccc3-c3nnn[nH]3)cc2)c(CC)n1 + CO`
  * 生成命中：`CCc1cc2c(cc(O)c(=O)n2Cc2ccc(-c3ccccc3-c3nnn[nH]3)cc2)c(CC)n1`
  * 记录产物：`Br ; Br.CCc1cc2c(cc(O)c(=O)n2Cc2ccc(-c3ccccc3-c3nnn[nH]3)cc2)c(CC)n1 ; CCc1cc2c(cc(O)c(=O)n2Cc2ccc(-c3ccccc3-c3nnn[nH]3)cc2)c(CC)n1`
* `ord-007dfb6ca4f6425b96640b84db3c395e`
  * 反应物：`BrB(Br)Br + CCOCC + COc1ccc2c(Oc3ccc(OCCN4CCCCC4)cc3)c(-c3cccc(F)c3F)ccc2c1 + Cl`
  * 生成命中：`Oc1ccc2c(Oc3ccc(OCCN4CCCCC4)cc3)c(-c3cccc(F)c3F)ccc2c1`
  * 记录产物：`Cl ; Cl.Oc1ccc2c(Oc3ccc(OCCN4CCCCC4)cc3)c(-c3cccc(F)c3F)ccc2c1 ; Oc1ccc2c(Oc3ccc(OCCN4CCCCC4)cc3)c(-c3cccc(F)c3F)ccc2c1`
* `ord-8c71e8b1b43542c088b9173ff8acf44a`
  * 反应物：`BrB(Br)Br + COc1ccccc1CCN(CCCCN1C(=O)CC2(CCCC2)CC1=O)C(C)C + N + O=C([O-])O.[Na+]`
  * 生成命中：`CC(C)N(CCCCN1C(=O)CC2(CCCC2)CC1=O)CCc1ccccc1O`
  * 记录产物：`CC(C)N(CCCCN1C(=O)CC2(CCCC2)CC1=O)CCc1ccccc1O`

### `decarboxylation_aromatic_001` 芳香酸脱羧

* `ord-2447bbbad4af4dbdb4ec6e34b3d8a503`
  * 反应物：`Cc1ccc2c(c1)c(C(=O)O)cc1ccc(Br)cc12 + O`
  * 生成命中：`Cc1ccc2c(ccc3ccc(Br)cc32)c1`
  * 记录产物：`Cc1ccc2c(ccc3ccc(Br)cc32)c1`

### `hydration_alkene_001` 烯烃水合

* `ord-167aa8ae8ea442419175105f9aef78c4`
  * 反应物：`B1C2CCCC1CCC2 + C=C1CCC(c2ccc(O[Si](C)(C)C(C)(C)C)cc2O[Si](C)(C)C(C)(C)C)CC1 + O=S(=O)([O-])S(=O)(=O)[O-].[Na+].[Na+] + OO`
  * 生成命中：`CC(C)(C)[Si](C)(C)Oc1ccc(C2CCC(CO)CC2)c(O[Si](C)(C)C(C)(C)C)c1`
  * 记录产物：`CC(C)(C)[Si](C)(C)Oc1ccc(C2CCC(CO)CC2)c(O[Si](C)(C)C(C)(C)C)c1`
* `ord-7f841c898eb748f4904cdc4b45b6335b`
  * 反应物：`B.C1CCOC1 + C=CC[C@]1(c2ccc(F)cc2)CCN([C@@H](C)c2ccc(OCC(F)(F)F)cc2)C(=O)O1`
  * 生成命中：`CC(c1ccc(OCC(F)(F)F)cc1)N1CCC(CCCO)(c2ccc(F)cc2)OC1=O`
  * 记录产物：`CC(c1ccc(OCC(F)(F)F)cc1)N1CCC(CCCO)(c2ccc(F)cc2)OC1=O`

### `oxidation_primary_alcohol_001` 伯醇氧化成醛

* `ord-94d09087271b4328a2c67bc52eba23b2`
  * 反应物：`O=[N+]([O-])c1ccc(-c2nn(-c3ccccc3)cc2CO)o1`
  * 生成命中：`O=Cc1cn(-c2ccccc2)nc1-c1ccc([N+](=O)[O-])o1`
  * 记录产物：`O=Cc1cn(-c2ccccc2)nc1-c1ccc([N+](=O)[O-])o1`
* `ord-6b72ab55819f44d887a00194ca641705`
  * 反应物：`CC(=O)Nc1ccccc1CO`
  * 生成命中：`CC(=O)Nc1ccccc1C=O`
  * 记录产物：`CC(=O)Nc1ccccc1C=O`
* `ord-397ea94fa22c4e2782fc007ec26d46a8`
  * 反应物：`O=C([O-])[O-].[K+].[K+] + O=C([O-])[O-].[Na+].[Na+] + O=C1CCC(=O)N1Br + OCc1ccnc(Cl)c1`
  * 生成命中：`O=Cc1ccnc(Cl)c1`
  * 记录产物：`O=Cc1ccnc(Cl)c1`

### `oxidation_sulfide_001` 硫醚氧化成亚砜

* `ord-77762fe0ea0b42919686e65eab98a63e`
  * 反应物：`CC(=O)OC(C)C + CC(C)c1ccccc1.[O-]O + CCN(C(C)C)C(C)C + CC[C@](O)(C(=O)[O-])[C@](O)(CC)C(=O)[O-]`
  * 生成命中：`Cc1c([N+](=O)[O-])ccnc1CS(=O)c1nc2ccccc2[nH]1`
  * 记录产物：`Cc1c([N+](=O)[O-])ccnc1CS(=O)c1nc2ccccc2[nH]1`
* `ord-ef5e5bb2c25643b9b914091572e20707`
  * 反应物：`COCCOCc1cc2cnc(SC)nc2n(C2CCCC2)c1=O + O=S(=O)(c1ccccc1)N1OC1c1ccccc1`
  * 生成命中：`COCCOCc1cc2cnc(S(C)=O)nc2n(C2CCCC2)c1=O`
  * 记录产物：`COCCOCc1cc2cnc(S(C)=O)nc2n(C2CCCC2)c1=O`
* `ord-5a949247749c476c9f40b7deb2a95806`
  * 反应物：`CCSCC(O)(C(=O)Nc1ccc(C#N)c(C(F)(F)F)c1)C(F)(F)F + [Na+].[O-][I+3]([O-])([O-])[O-]`
  * 生成命中：`CCS(=O)CC(O)(C(=O)Nc1ccc(C#N)c(C(F)(F)F)c1)C(F)(F)F`
  * 记录产物：`CCS(=O)CC(O)(C(=O)Nc1ccc(C#N)c(C(F)(F)F)c1)C(F)(F)F`

### `oxidation_epoxide_001` 双键环氧化

* `ord-5cd745230f16451da89bf64edf0df283`
  * 反应物：`COc1cc(C)cc(C/C=C(\C)CC/C=C(\C)CCC=C(C)C)c1 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`COc1cc(C)cc(CC=C(C)CCC=C(C)CCC2OC2(C)C)c1`
  * 记录产物：`COc1cc(C)cc(CC=C(C)CCC=C(C)CCC2OC2(C)C)c1`

### `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基

* `ord-e22e3fdd8818442586447102a6833261`
  * 反应物：`CCCOc1ccc2c(c1)C(=O)C(C(=O)OC)C2c1ccc2c(c1)OCO2`
  * 生成命中：`CCCOc1ccc2c(c1)C(=O)C(C(=O)OC)=C2c1ccc2c(c1)OCO2`
  * 记录产物：`CCCOc1ccc2c(c1)C(=O)C(C(=O)OC)=C2c1ccc2c(c1)OCO2`
* `ord-7e1b8c4af1cf411cb56c15207b9e276a`
  * 反应物：`O=C([O-])[O-].[K+].[K+] + O=C1CCc2ccc(OCCCCN3CCCN(c4cccc(Cl)c4Cl)CC3)cc2N1 + O=c1ccc2ccc(OCCCCBr)cc2[nH]1 + [I-].[Na+]`
  * 生成命中：`O=c1ccc2ccc(OCCCCN3CCCN(c4cccc(Cl)c4Cl)CC3)cc2[nH]1`
  * 记录产物：`O=c1ccc2ccc(OCCCCN3CCCN(c4cccc(Cl)c4Cl)CC3)cc2[nH]1`

### `reduction_aldehyde_001` 醛还原成醇

* `ord-75ae478bd80e476b9173572378913963`
  * 反应物：`COC(=O)[C@H](Cc1ccc(-c2ccccc2C=O)cc1)NC(=O)c1c(Cl)cccc1Cl + [BH4-].[Na+]`
  * 生成命中：`COC(=O)C(Cc1ccc(-c2ccccc2CO)cc1)NC(=O)c1c(Cl)cccc1Cl`
  * 记录产物：`COC(=O)C(Cc1ccc(-c2ccccc2CO)cc1)NC(=O)c1c(Cl)cccc1Cl`
* `ord-7ac2925b5dce498d80b980bf5237a360`
  * 反应物：`CC[C@H]1CN(C2COC2)CCN1c1ccc(Nc2cc(-c3ccnc(-n4ccn5c6c(cc5c4=O)CCCC6)c3C=O)cn(C)c2=O)nc1 + [BH4-].[Na+]`
  * 生成命中：`CCC1CN(C2COC2)CCN1c1ccc(Nc2cc(-c3ccnc(-n4ccn5c6c(cc5c4=O)CCCC6)c3CO)cn(C)c2=O)nc1`
  * 记录产物：`CCC1CN(C2COC2)CCN1c1ccc(Nc2cc(-c3ccnc(-n4ccn5c6c(cc5c4=O)CCCC6)c3CO)cn(C)c2=O)nc1`
* `ord-4f2eb161733649c29e5af72a0f020f30`
  * 反应物：`N#Cc1ccc(CCN2CCC(O)(COc3ccc(C=O)cc3)CC2)cc1 + O + [BH4-].[Na+]`
  * 生成命中：`N#Cc1ccc(CCN2CCC(O)(COc3ccc(CO)cc3)CC2)cc1`
  * 记录产物：`N#Cc1ccc(CCN2CCC(O)(COc3ccc(CO)cc3)CC2)cc1`

### `reduction_alkene_001` 双键加氢

* `ord-3640c8aaa94d4416a6841f2457352d20`
  * 反应物：`COc1ccc(C=CCCCCn2ccnc2)cc1.Cl + O + O=C([O-])O.[Na+] + [H][H]`
  * 生成命中：`COc1ccc(CCCCCCn2ccnc2)cc1`
  * 记录产物：`COc1ccc(CCCCCCn2ccnc2)cc1`
* `ord-384efdd748d44cbdb11fe89a68d718f5`
  * 反应物：`COc1ccc2c(c1)OCC(c1ccc(C(F)(F)F)cc1)=C2c1ccc(O)cc1`
  * 生成命中：`COc1ccc2c(c1)OCC(c1ccc(C(F)(F)F)cc1)C2c1ccc(O)cc1`
  * 记录产物：`COc1ccc2c(c1)OCC(c1ccc(C(F)(F)F)cc1)C2c1ccc(O)cc1`
* `ord-685e5399c72a4dd2b503de07f3ed0f9c`
  * 反应物：`CCOC(=O)C=C1CCn2c1cc1c(C)c(OC)ccc12`
  * 生成命中：`CCOC(=O)CC1CCn2c1cc1c(C)c(OC)ccc12`
  * 记录产物：`CCOC(=O)CC1CCn2c1cc1c(C)c(OC)ccc12`

### `reduction_nitro_001` 硝基还原成胺

* `ord-3805bcf4ac35487b889e58f78d128e4e`
  * 反应物：`O=C(Nc1cc(-c2cnccn2)ccc1[N+](=O)[O-])N1CCCC1`
  * 生成命中：`Nc1ccc(-c2cnccn2)cc1NC(=O)N1CCCC1`
  * 记录产物：`Nc1ccc(-c2cnccn2)cc1NC(=O)N1CCCC1`
* `ord-dd1ed04a0aff4fbd85a039e52bf1a545`
  * 反应物：`Cc1ccc(O)c([N+](=O)[O-])n1`
  * 生成命中：`Cc1ccc(O)c(N)n1`
  * 记录产物：`Cc1ccc(O)c(N)n1`
* `ord-ab057e4eff6a47699dacc390c5395e1e`
  * 反应物：`O=C1c2ccc([N+](=O)[O-])cc2C(=O)N1CCO + [H][H]`
  * 生成命中：`Nc1ccc2c(c1)C(=O)N(CCO)C2=O`
  * 记录产物：`Nc1ccc2c(c1)C(=O)N(CCO)C2=O`

### `hydrolysis_lactam_001` 内酰胺开环

* `ord-3f15bf221dc54fad9271a09bdff7e39f`
  * 反应物：`C=CCOC(=O)N(Cc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1)C(C)(C)C + CCN(C(C)C)C(C)C`
  * 生成命中：`CC(C)(C)NCc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1`
  * 记录产物：`CC(C)(C)NCc1cccc(-c2ccnc(NCCc3ccc(O)c(Cl)c3)n2)c1`
* `ord-6fd8d293355045979e6505dd8785f092`
  * 反应物：`O=C(OCc1ccccc1)N1CCC(N2CCCCCC2=O)CC1`
  * 生成命中：`O=C1CCCCCN1C1CCNCC1`
  * 记录产物：`O=C1CCCCCN1C1CCNCC1`
* `ord-293c5493b0564c5dbb41fd0b42172a02`
  * 反应物：`C=CC(Cl)=C(Cl)Cl + CC(C)C(=O)N(C)C + CCN(CC)CC + O`
  * 生成命中：`CNC`
  * 记录产物：`C=CC(Cl)=C(Cl)Cl ; CNC`

### `hydrolysis_imine_001` 亚胺水解

* `ord-e32b9968b3dc4b0aa05fbebfe7aa9b79`
  * 反应物：`CCCn1c(=O)cc(N=CN(C)C)n(CC)c1=O`
  * 生成命中：`CCCn1c(=O)cc(N)n(CC)c1=O`
  * 记录产物：`CCCn1c(=O)cc(N)n(CC)c1=O`

### `isomerization_epimerization_001` 差向异构化

* `ord-92a446f0ee374bf5b6f980c4166659da`
  * 反应物：`C/C1=C2N=C(/C=C3N=C(/C(C)=C4\[N-][C@@](C)([C@@H]5N=C1[C@](C)(CCC(=O)NC[C@@H](C)OP(=O)([O-])O[C@H]1[C@@H](O)[C@@H](n6cnc7cc(C)c(C)cc76)O[C@@H]1CO)[C@H]5CC(N)=O)[C@@](C)(CC(N)=O)[C@@H]4CCC(N)=O)[C@@](C)(CC(N)=O)[C@@H]\3CCC(N)=O)C(C)(C)[C@@H]/2CCC(N)=O.[C-]#N.[Co+3] + C[S+](C)C.[Br-] + O.O.O.O.O.O.[Cl][Co][Cl] + [BH4-].[Na+]`
  * 生成命中：`CC1=C2N=C(C=C3N=C(C(C)=C4[N-]C(C)(C5N=C1C(C)(CCC(=O)NCC(C)OP(=O)([O-])OC1C(CO)OC(n6cnc7cc(C)c(C)cc76)C1O)C5CC(N)=O)C(C)(CC(N)=O)C4CCC(N)=O)C(C)(CC(N)=O)C3CCC(N)=O)C(C)(C)C2CCC(N)=O`
  * 记录产物：`CC1=C2N=C(C=C3N=C(C(C)=C4[N-]C(C)(C5N=C1C(C)(CCC(=O)NCC(C)OP(=O)([O-])OC1C(CO)OC(n6cnc7cc(C)c(C)cc76)C1O)C5CC(N)=O)C(C)(CC(N)=O)C4CCC(N)=O)C(C)(CC(N)=O)C3CCC(N)=O)C(C)(C)C2CCC(N)=O ; CC1=C2N=C(C=C3N=C(C(C)=C4[N-]C(C)(C5N=C1C(C)(CCC(=O)NCC(C)OP(=O)([O-])OC1C(CO)OC(n6cnc7cc(C)c(C)cc76)C1O)C5CC(N)=O)C(C)(CC(N)=O)C4CCC(N)=O)C(C)(CC(N)=O)C3CCC(N)=O)C(C)(C)C2CCC(N)=O.[CH3-].[Co+3] ; [CH3-] ; [Co+3]`
* `ord-704c341d0813481cb1f59574402cd31a`
  * 反应物：`C=O + CC(C)(CO)[C@@H](O)C(=O)NCCC(=O)O + CC1(C)COC(=O)C1O + [C-]#N`
  * 生成命中：`CC(C)(CO)C(O)C(=O)NCCC(=O)O`
  * 记录产物：`CC(C)(CO)C(O)C(=O)NCCC(=O)O`
* `ord-93de1bc3f38c47fa8ca9e0ef0a65e0f1`
  * 反应物：`CC(C)O.O=C=O + COc1cc([N+](=O)[O-])ccc1OCC(O)C1CC1`
  * 生成命中：`COc1cc([N+](=O)[O-])ccc1OCC(O)C1CC1`
  * 记录产物：`COc1cc([N+](=O)[O-])ccc1OCC(O)C1CC1`

### `elimination_deamination_001` 氧化脱氨成羰基

* `ord-880ac37b3955411491cae66a6889f58c`
  * 反应物：`NCc1ccccc1 + O=c1ccc2c([C@@H]3CO3)ccc(OCc3ccccc3)c2[nH]1`
  * 生成命中：`N`
  * 记录产物：`N ; O=c1ccc2c(C(O)CNCc3ccccc3)ccc(OCc3ccccc3)c2[nH]1`

### `esterification_transesterification_001` 酯交换

* `ord-da7d24e50de54b24b7fe7918c9ca080e`
  * 反应物：`C/C=C1/CC[C@H]2[C@@H]3CC[C@@H]4C[C@H](O)CC[C@]4(C)C3=CC[C@]12C + CC(=O)OC(C)=O + CCN(CC)CC`
  * 生成命中：`CC=C1CCC2C3CCC4CC(OC(C)=O)CCC4(C)C3=CCC12C`
  * 记录产物：`CC=C1CCC2C3CCC4CC(OC(C)=O)CCC4(C)C3=CCC12C`
* `ord-8ec3de83649d46f48767e73c7b85adb4`
  * 反应物：`CC(=O)OC(C)=O + CCCC(C)(C)O + CCCC(C)CO + CCCCC(C)(C)OC(C)=O`
  * 生成命中：`CCCC(C)(C)OC(C)=O`
  * 记录产物：`CCCC(C)(C)OC(C)=O`
* `ord-04f56364fadf44e08985a30ea1878d23`
  * 反应物：`CCOC(=O)C1CCCC1=O + OCc1ccccc1`
  * 生成命中：`O=C1CCCC1C(=O)OCc1ccccc1`
  * 记录产物：`O=C1CCCC1C(=O)OCc1ccccc1`

### `esterification_intermolecular_001` 酯化(分子间)

* `ord-f2832b5fb09b4e59ad1cd227ee44f57d`
  * 反应物：`C=CCC[C@@H](O)C[C@@H]1OC(=O)[C@H]1CCCCCC + CC(C)C[C@H](NC=O)C(=O)O`
  * 生成命中：`C=CCCC(CC1OC(=O)C1CCCCCC)OC(=O)C(CC(C)C)NC=O`
  * 记录产物：`C=CCCC(CC1OC(=O)C1CCCCCC)OC(=O)C(CC(C)C)NC=O`
* `ord-265a8ac770d84602a10c187a79d1e14e`
  * 反应物：`C=C1CCCCCCCSC[C@@H](C(=O)O)NC1=O + CCO`
  * 生成命中：`C=C1CCCCCCCSCC(C(=O)OCC)NC1=O`
  * 记录产物：`C=C1CCCCCCCSCC(C(=O)OCC)NC1=O`
* `ord-82ac35b47d49457a8ca10c50a8933329`
  * 反应物：`CC(=O)OC(C)=O + Cc1ccc2c(=O)c(C(=O)O)cn(CCO)c2n1 + O=CO`
  * 生成命中：`Cc1ccc2c(=O)c(C(=O)O)cn(CCOC=O)c2n1`
  * 记录产物：`Cc1ccc2c(=O)c(C(=O)O)cn(CCOC=O)c2n1`

### `condensation_schiff_base_001` 席夫碱生成

* `ord-696de05f6c3a4ea4b5110db9d813a8de`
  * 反应物：`Cc1ccc(S(=O)(=O)O)cc1 + NCc1ccccc1 + O=Cc1ccccc1O`
  * 生成命中：`Oc1ccccc1C=NCc1ccccc1`
  * 记录产物：`Oc1ccccc1C=NCc1ccccc1`

### `amidation_intermolecular_001` 酰胺化(分子间)

* `ord-91c62d2f07f84c8dbeb530ddca5c965b`
  * 反应物：`CC1(C)OC[C@@H](Cn2ccc(N)n2)O1 + CCN(C(C)C)C(C)C + CN(C)[P+](On1nnc2ccccc21)(N(C)C)N(C)C.F[P-](F)(F)(F)(F)F + CSCC[C@@H](C(=O)O)N1CC(Oc2ccccc2Cl)=CC1=O`
  * 生成命中：`CSCCC(C(=O)Nc1ccn(CC2COC(C)(C)O2)n1)N1CC(Oc2ccccc2Cl)=CC1=O`
  * 记录产物：`CSCCC(C(=O)Nc1ccn(CC2COC(C)(C)O2)n1)N1CC(Oc2ccccc2Cl)=CC1=O`
* `ord-a69d79bf012b428b92a0d27d2b970d59`
  * 反应物：`CCN(C(C)C)C(C)C + CN(C)C(On1nnc2ccccc21)=[N+](C)C.F[P-](F)(F)(F)(F)F + C[C@@H](C(=O)O)N(C)C(=O)OC(C)(C)C + N[C@H](C(=O)N1CCC[C@H]1c1cccc(Oc2ccccc2)c1)C1CCCCC1`
  * 生成命中：`CC(C(=O)NC(C(=O)N1CCCC1c1cccc(Oc2ccccc2)c1)C1CCCCC1)N(C)C(=O)OC(C)(C)C`
  * 记录产物：`CC(C(=O)NC(C(=O)N1CCCC1c1cccc(Oc2ccccc2)c1)C1CCCCC1)N(C)C(=O)OC(C)(C)C`
* `ord-7eeb847fb10b4250a4983948580c084f`
  * 反应物：`C[C@@H]1CCCN[C@@H]1CNc1ccc(C(F)(F)F)cn1 + Cc1ccc(-c2cncs2)c(C(=O)O)c1`
  * 生成命中：`Cc1ccc(-c2cncs2)c(C(=O)N2CCCC(C)C2CNc2ccc(C(F)(F)F)cn2)c1`
  * 记录产物：`Cc1ccc(-c2cncs2)c(C(=O)N2CCCC(C)C2CNc2ccc(C(F)(F)F)cn2)c1`

### `aminolysis_ester_001` 酯的氨解

* `ord-2aaa495b46bc4d9b8a75a64dde900409`
  * 反应物：`CC(=O)OC(C)=O + CSC[C@H](N)C(=O)O + Cl + [Na+].[OH-]`
  * 生成命中：`CSCC(NC(C)=O)C(=O)O`
  * 记录产物：`CSCC(NC(C)=O)C(=O)O`
* `ord-c2cf5a8b693e452dbf19d3e2ee0ac7cf`
  * 反应物：`CCN(C(C)C)C(C)C + CS(C)=O + Cc1ccc(-n2nc(C(C)(C)C)cc2NC(=O)OCC(Cl)(Cl)Cl)cc1 + Nc1ccc(-c2ccc(CN3CCOCC3)o2)c2ccccc12`
  * 生成命中：`Cc1ccc(-n2nc(C(C)(C)C)cc2NC(=O)Nc2ccc(-c3ccc(CN4CCOCC4)o3)c3ccccc23)cc1`
  * 记录产物：`Cc1ccc(-n2nc(C(C)(C)C)cc2NC(=O)Nc2ccc(-c3ccc(CN4CCOCC4)o3)c3ccccc23)cc1`
* `ord-6b847f7deeb44919b6b71cf88c9f7711`
  * 反应物：`CCOC(=O)n1c(C(=O)c2ccccc2)c(N)c2ccc([N+](=O)[O-])cc21 + CCOC(C)=O`
  * 生成命中：`CCOC(=O)n1c(C(=O)c2ccccc2)c(NC(C)=O)c2ccc([N+](=O)[O-])cc21`
  * 记录产物：`CCOC(=O)n1c(C(=O)c2ccccc2)c(NC(C)=O)c2ccc([N+](=O)[O-])cc21`

### `condensation_aldol_001` 醇醛缩合(分子间)

* `ord-5faf9a9442e24816b9ff9951478faafc`
  * 反应物：`CCN(CC)CC + CCOC(=O)C=O + O=C(Cc1ccc(OC2CCCCC2)cc1)C1CCCCC1`
  * 生成命中：`CCOC(=O)C(O)C(C(=O)C1CCCCC1)c1ccc(OC2CCCCC2)cc1`
  * 记录产物：`CCOC(=O)C(O)C(C(=O)C1CCCCC1)c1ccc(OC2CCCCC2)cc1`

### `elimination_amide_to_nitrile_001` 酰胺脱水成腈

* `ord-e9274e4c4fed4362a879e98a886da25c`
  * 反应物：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC(N)=O)CO3)cc1 + O + O=C(OC(=O)C(F)(F)F)C(F)(F)F + c1ccncc1`
  * 生成命中：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC#N)CO3)cc1`
  * 记录产物：`CCCCCc1ccc(C=CC(=O)Nc2cccc3c2OC(CC#N)CO3)cc1`

## 失败/无命中说明

* 没有 `product_match` 的规则不等于“规则错”：可能是 ORD 抽样里没有该反应类型、底物取代基不匹配、规则要求多步/共试剂，或记录方向相反。
* `run_errors` 是 RDKit 在具体底物上抛错的次数，已逐条累计；`invalid_products` 是生成物无法规范化的次数。
* 需要外部权威规则来源时，下一步应查论文/数据集原文；本报告只回答“有没有在 ORD 真实记录里跑出相同产物”。
