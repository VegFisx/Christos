# 第七十五轮 · 规则来源体检（ORD 真实反应实测）

> **做法**：把每条规则的 SMARTS 套到 ORD 真实记录的**反应物**上，生成产物经「去映射号 / 去显式 H / 去立体 / 拆片段」规范化，再与记录的真实产物比对。
> **product_match** = 生成片段与该记录真实产物有交集；**fired** = 规则至少生成过一个可解析产物。

## 口径（先看这段）

* 数据源：`D:\ProgramData\DSHNS\chemreact-staging\data\ord_reaction_index.jsonl`，共 1,770,980 行；按步长 14 等距抽样，实际扫描 **119,993** 条。
* 这是**前向试跑**，不是逆合成审计；ORD 记录未必是同一反应类型，所以 `fired` 多不代表规则对，只代表底物里存在可匹配子结构。
* 规则里的水/共试剂多为**隐含**（如水解规则不把 H2O 写成反应物），因此本审计只把规则套到记录的反应物列；这比方案 a 的模板签名更接近真实用法。
* 规范化忽略立体与显式 H；`product_match` 是**分子图相同**，不是条件/机理相同。
* 只给计数与样例，**不打分、不排序**；`rules.json` 原顺序。

## 总览

* 规则：**73** 条（{'论文修正': 8, '论文原样': 10, '自写新增': 55}）
* 至少 `fired` 一次：**66** 条
* 至少 `product_match` 一次：**56** 条
* 反应物解析失败：**0** 次；产物解析失败：**0** 次

## 逐条结果

| # | 规则 | 类别 | 状态 | 论文档位 | fired | product_match | run_errors | 首个命中 rid |
|---|---|---|---|---|---|---|---|---|
| 1 | `hydrolysis_amide_001` 酰胺水解 | hydrolysis | active | 论文修正 | 42033 | 3362 | 0 | ord-b5c1249063ad41ecb9a886e640b8e144 |
| 2 | `hydrolysis_sulfate_001` 硫酸酯水解 | hydrolysis | active | 论文原样 | 1593 | 9 | 0 | ord-38fad87017304b2ea8cf82845de81665 |
| 3 | `hydrolysis_phosphate_001` 磷酸酯水解 | hydrolysis | active | 论文原样 | 778 | 6 | 0 | ord-b76832d8c2fe47609a139e614967c486 |
| 4 | `hydrolysis_acetal_001` 缩醛水解 | hydrolysis | active | 论文修正 | 2175 | 213 | 0 | ord-991308a13d764cc0817ac696051b408e |
| 5 | `hydrolysis_hemiacetal_001` 半缩醛水解 | hydrolysis | active | 论文原样 | 155 | 1 | 0 | ord-26bde17dc5b64039ae34d2762669f729 |
| 6 | `oxidation_hydroxyl_001` 羟基氧化 | oxidation | active | 论文原样 | 7878 | 346 | 0 | ord-518a16e34f3943a5b14400a699394dc9 |
| 7 | `oxidation_aldehyde_001` 醛氧化 | oxidation | active | 论文原样 | 10671 | 126 | 0 | ord-3241ab6c22d447b498b7ce647cbfc9d9 |
| 8 | `oxidation_phenol_quinone_001` 酚氧化成醌 | oxidation | active | 论文原样 | 255 | 0 | 0 | — |
| 9 | `oxidation_amine_001` 胺氧化 | oxidation | active | 论文修正 | 6522 | 13 | 0 | ord-4f7a9ea9dccc4c679c1789f679ee250a |
| 10 | `reduction_ketone_001` 酮还原 | reduction | active | 论文原样 | 82068 | 955 | 0 | ord-59ad5f10a39944bab640d9fbd6671548 |
| 11 | `reduction_quinone_001` 醌还原 | reduction | active | 论文修正 | 290 | 0 | 0 | — |
| 12 | `demethylation_aromatic_001` 脱甲基 | demethylation | active | 论文修正 | 15300 | 686 | 0 | ord-c366215603d74e8f80c204c070b5fd26 |
| 13 | `decarboxylation_aromatic_001` 芳香酸脱羧 | decarboxylation | active | 论文原样 | 7912 | 58 | 0 | ord-a6d16c84992d44c5ba2388e74f39994d |
| 14 | `decarboxylation_beta_keto_001` β-酮酸脱羧 | decarboxylation | active | 论文修正 | 263 | 13 | 0 | ord-3106a99bd54c4b21ada04ba10d9f7f30 |
| 15 | `hydroxylation_aromatic_001` 芳香环羟基化 | hydroxylation | active | 论文原样 | 109923 | 35 | 0 | ord-49d570f5b6da402d8ae3be1663819276 |
| 16 | `hydration_alkene_001` 烯烃水合 | hydration | active | 论文原样 | 15883 | 70 | 0 | ord-b8c3fa2dbf1b481391b010440c8960b9 |
| 17 | `hydration_enone_001` α,β-不饱和羰基水合 | hydration | active | 论文修正 | 6864 | 5 | 0 | ord-6b5f322ea8cd4872a6831d2085442628 |
| 18 | `tautomerization_keto_enol_001` 酮-烯醇化 | rearrangement | active | 论文修正 | 53620 | 0 | 0 | — |
| 19 | `esterification_gamma_lactone_001` γ-内酯化 | esterification | active | 自写新增 | 80 | 0 | 0 | — |
| 20 | `esterification_delta_lactone_001` δ-内酯化 | esterification | active | 自写新增 | 36 | 1 | 0 | ord-87b35a6264bb4aac9c89aeef80b41113 |
| 21 | `oxidation_primary_alcohol_001` 伯醇氧化成醛 | oxidation | active | 自写新增 | 10894 | 524 | 0 | ord-8547a040ad9a425c98f22d4b4c6c403c |
| 22 | `oxidation_sulfide_001` 硫醚氧化成亚砜 | oxidation | active | 自写新增 | 9960 | 336 | 0 | ord-0390e1237c0d4ce1b863fbe6e79e9218 |
| 23 | `oxidation_epoxide_001` 双键环氧化 | oxidation | active | 自写新增 | 15883 | 103 | 0 | ord-07e7b8d911554e5d89dde51561daed3a |
| 24 | `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基 | oxidation | active | 自写新增 | 30833 | 41 | 0 | ord-722cf82db39c409eb44cd3dedcb941d6 |
| 25 | `reduction_aldehyde_001` 醛还原成醇 | reduction | active | 自写新增 | 10671 | 313 | 0 | ord-c63ace3342d84bbd8c5c2007a1065d40 |
| 26 | `reduction_alkene_001` 双键加氢 | reduction | active | 自写新增 | 15883 | 747 | 0 | ord-a2fcb8e364ca4dd2ada72db56fde3611 |
| 27 | `hydrolysis_lactam_001` 内酰胺开环 | hydrolysis | active | 自写新增 | 29910 | 2750 | 0 | ord-b5c1249063ad41ecb9a886e640b8e144 |
| 28 | `hydrolysis_imine_001` 亚胺水解 | hydrolysis | active | 自写新增 | 330 | 21 | 0 | ord-b1dcbef1739948fe87cc9c46b0f68caa |
| 29 | `cyclization_hemiacetal_001` 分子内半缩醛化 | cyclization | active | 自写新增 | 96 | 0 | 0 | — |
| 30 | `cyclization_lactam_001` 分子内酰胺化 | cyclization | active | 自写新增 | 54 | 2 | 0 | ord-b80adfa3516a434db141f13b4adac7f3 |
| 31 | `cyclization_ether_001` 分子内脱水成醚 | cyclization | active | 自写新增 | 540 | 8 | 0 | ord-a5fb5c3cc7cf4d64ad4d21d86b8e6e50 |
| 32 | `cyclization_lactone_delta_001` δ-羟基酸内酯化(备用) | cyclization | active | 自写新增 | 36 | 1 | 0 | ord-87b35a6264bb4aac9c89aeef80b41113 |
| 33 | `isomerization_double_bond_001` 双键位置异构 | rearrangement | active | 自写新增 | 3541 | 22 | 0 | ord-4d2a5ce25ca84394ba1e3974ebce74f6 |
| 34 | `rearrangement_retro_aldol_001` 逆羟醛裂解 | rearrangement | active | 自写新增 | 1719 | 15 | 0 | ord-3106a99bd54c4b21ada04ba10d9f7f30 |
| 35 | `decarboxylation_malonic_001` 丙二酸型脱羧 | decarboxylation | active | 自写新增 | 263 | 13 | 0 | ord-3106a99bd54c4b21ada04ba10d9f7f30 |
| 36 | `elimination_deamination_001` 氧化脱氨成羰基 | elimination | active | 自写新增 | 6522 | 13 | 0 | ord-4f7a9ea9dccc4c679c1789f679ee250a |
| 37 | `esterification_transesterification_001` 酯交换 | esterification | active | 自写新增 | 15194 | 321 | 0 | ord-00533d2621284180b8d6e372c9496cb7 |
| 38 | `esterification_intermolecular_001` 酯化(分子间) | esterification | active | 自写新增 | 26232 | 998 | 0 | ord-c6d1437bef5145cca37826ac5ae090f0 |
| 39 | `condensation_schiff_base_001` 席夫碱生成 | condensation | active | 自写新增 | 2571 | 142 | 0 | ord-968da5d345074707bd8ae7f036b4987e |
| 40 | `amidation_intermolecular_001` 酰胺化(分子间) | condensation | active | 自写新增 | 17414 | 6006 | 0 | ord-21393e26ab0b4c64a67d4dbe4b4c6328 |
| 41 | `aminolysis_ester_001` 酯的氨解 | condensation | active | 自写新增 | 23459 | 1249 | 0 | ord-9db8bda42ddd42569da026335543c4dd |
| 42 | `condensation_glycosylation_001` 糖苷化 | condensation | active | 自写新增 | 155 | 4 | 0 | ord-0c6d074bda374bf1ac9566888c34446c |
| 43 | `condensation_hemiacetal_001` 半缩醛形成(分子间) | condensation | active | 自写新增 | 4200 | 0 | 0 | — |
| 44 | `addition_michael_thiol_001` Michael加成(硫醇) | addition | active | 自写新增 | 138 | 28 | 0 | ord-d9dbb8c843704e72b8d436d338439278 |
| 45 | `addition_michael_amine_001` Michael加成(胺) | addition | active | 自写新增 | 3821 | 76 | 0 | ord-41d35a48018a4cf78bfe4a9b41deea1d |
| 46 | `condensation_aldol_001` 醇醛缩合(分子间) | condensation | active | 自写新增 | 53620 | 75 | 0 | ord-eb2ffed42db34070991af4f46a60fd88 |
| 47 | `addition_thiohemiacetal_001` 硫代半缩醛形成 | addition | active | 自写新增 | 134 | 0 | 0 | — |
| 48 | `elimination_amide_to_nitrile_001` 酰胺脱水成腈 | elimination | active | 自写新增 | 2755 | 122 | 0 | ord-4de2e5c5af6b486c8884eeb767fb4238 |
| 49 | `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜 | oxidation | active | 自写新增 | 3653 | 26 | 0 | ord-7cbd6652612f4c55b07a8147385f28b2 |
| 50 | `reduction_sulfoxide_001` 亚砜还原成硫醚 | reduction | active | 自写新增 | 3653 | 9 | 0 | ord-9bd323dfdfc3445abcf8bcd679f410ce |
| 51 | `decarboxylation_cinnamic_001` 肉桂酸型脱羧 | decarboxylation | active | 自写新增 | 270 | 0 | 0 | — |
| 52 | `oxidation_diphenol_para_001` 对二酚氧化成醌 | oxidation | active | 自写新增 | 165 | 6 | 0 | ord-5e6a35ae7d31484597e3dd3d9eaeb9f3 |
| 53 | `reduction_quinone_para_001` 对醌还原成二酚 | reduction | active | 自写新增 | 314 | 5 | 0 | ord-d264a4b8ce364c998253ee55ac74f6a8 |
| 54 | `cyclization_conrad_limpach_alpha_aryl_001` Conrad–Limpach 喹啉酮合成（α-芳基 β-酮酯） | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 55 | `cyclization_indazole_001` 邻卤二苯甲酮 + 芳基肼 -> 1,2-二芳基吲唑 | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 56 | `cyclization_fischer_aza_indole_001` Fischer 氮杂吲哚合成（2-肼基吡啶 + α-芳基酮） | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 57 | `cyclization_larock_indole_001` Larock 吲哚合成（2-碘苯胺 + TMS 炔） | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 58 | `cyclization_hantzsch_thiazole_001` Hantzsch 噻唑合成（环状 α-溴酮 + 硫代氨基脲） | cyclization | active | 自写新增 | 0 | 0 | 0 | — |
| 59 | `cyclization_macro_lactam_001` 大环内酰胺化（同一分子内羧酸 + 铵盐） | cyclization | active | 自写新增 | 172 | 14 | 0 | ord-c763472b558f4bf19c166b3b739155cb |
| 60 | `deprotection_boc_amine_001` Boc 保护的胺脱保护（热/酸解脱 Boc） | deprotection | active | 自写新增 | 1 | 0 | 0 | — |
| 61 | `deprotection_cbz_amine_001` Cbz 保护的胺脱保护（氢解 Cbz） | deprotection | active | 自写新增 | 0 | 0 | 0 | — |
| 62 | `sulfonylation_amine_001` 胺的磺酰化（磺酰氯 + 胺 -> 磺酰胺） | acylation | active | 自写新增 | 2 | 0 | 0 | — |
| 63 | `addition_isocyanate_amine_urea_001` 异氰酸酯 + 胺 -> 脲 | addition | active | 自写新增 | 1 | 1 | 0 | ord-c855ba8a68d94a90a16f7359111ea10d |
| 64 | `coupling_suzuki_biaryl_001` Suzuki 偶联（芳基溴 + 芳基硼酸 -> 联苯） | coupling | active | 自写新增 | 1160 | 920 | 0 | ord-19b3524e42254cd798a618b4d5e376b5 |
| 65 | `coupling_sonogashira_aryl_alkyne_001` Sonogashira 偶联（芳基溴 + 端炔 -> 芳基炔） | coupling | active | 自写新增 | 381 | 287 | 0 | ord-0dbb83c791174a899436c4d40bf3aa58 |
| 66 | `coupling_n_arylation_amine_001` Buchwald–Hartwig 型 N-芳基化（芳基溴 + 胺） | coupling | active | 自写新增 | 1516 | 149 | 0 | ord-e666274769674ed785f5d9ad4ef36895 |
| 67 | `coupling_n_alkylation_amine_001` 胺的 N-烷基化（卤代烷 + 胺 -> 仲/叔胺） | coupling | active | 自写新增 | 0 | 0 | 0 | — |
| 68 | `acylation_alcohol_anhydride_001` 醇的 O-酰化（酸酐 + 醇 -> 酯） | acylation | active | 自写新增 | 487 | 145 | 0 | ord-00533d2621284180b8d6e372c9496cb7 |
| 69 | `substitution_alcohol_thionyl_001` 醇的氯代（醇 + 亚硫酰氯 -> 氯代烷） | substitution | active | 自写新增 | 35 | 6 | 0 | ord-c9fda451c4c64a4baef159b8914061f8 |
| 70 | `substitution_alcohol_thionyl_family_001` 醇的氯代（伯/仲/苄醇族 + 亚硫酰氯） | substitution | active | 自写新增 | 525 | 307 | 0 | ord-b1be6064558b4bf8b5568e3fb5a9afe1 |
| 71 | `coupling_n_alkylation_benzyl_001` 苄基/杂芳甲基氯的 N-烷基化 | coupling | active | 自写新增 | 210 | 63 | 0 | ord-5552549c3a7244c2a7f25a78047820a8 |
| 72 | `acylation_alcohol_cyclic_succinic_001` 醇的 O-酰化（丁二酸酐开环 -> 单酯） | acylation | active | 自写新增 | 54 | 18 | 0 | ord-d8d5f6909a9d42dca945fc4afe484978 |
| 73 | `acylation_alcohol_cyclic_phthalic_001` 醇的 O-酰化（邻苯二甲酸酐开环 -> 单酯） | acylation | active | 自写新增 | 59 | 6 | 0 | ord-3dbead96b25644bab899c35c4bc7ec16 |

## 命中样例（前 3 条）

### `hydrolysis_amide_001` 酰胺水解

* `ord-b5c1249063ad41ecb9a886e640b8e144`
  * 反应物：`CC(C)(C)OC(=O)N1CCN(c2ccc3oc(C(N)=O)cc3c2)CC1`
  * 生成命中：`NC(=O)c1cc2cc(N3CCNCC3)ccc2o1`
  * 记录产物：`NC(=O)c1cc2cc(N3CCNCC3)ccc2o1`
* `ord-fe0aa9a207b24d63bb0ea46174e05e6e`
  * 反应物：`CC(=O)Nc1ccc2c(c1)OCc1ccsc1C2=O + O=C([O-])O.[Na+]`
  * 生成命中：`Nc1ccc2c(c1)OCc1ccsc1C2=O`
  * 记录产物：`Nc1ccc2c(c1)OCc1ccsc1C2=O`
* `ord-65e718a8f3934e1487660a0d4b652d2f`
  * 反应物：`C=CCOC(=O)[C@@H](CCc1ccccc1)NC(=O)OC(C)(C)C + COc1ccccc1 + O=C(O)C(F)(F)F + O=C([O-])O.[Na+]`
  * 生成命中：`C=CCOC(=O)C(N)CCc1ccccc1`
  * 记录产物：`C=CCOC(=O)C(N)CCc1ccccc1`

### `hydrolysis_sulfate_001` 硫酸酯水解

* `ord-38fad87017304b2ea8cf82845de81665`
  * 反应物：`COS(=O)(=O)C(F)(F)F + Cc1nccn1S(=O)(=O)N1CCN(C(=O)OC(C)(C)C)CC1`
  * 生成命中：`O=S(=O)(O)C(F)(F)F`
  * 记录产物：`Cc1nccn1S(=O)(=O)N1CCN(C(=O)OC(C)(C)C)CC1 ; Cc1nccn1S(=O)(=O)N1CCN(C(=O)OC(C)(C)C)CC1.O=S(=O)(O)C(F)(F)F ; O=S(=O)(O)C(F)(F)F`
* `ord-e785ea6338194dd69e22ecc6c663d32e`
  * 反应物：`CCCOS(=O)(=O)c1ccc(C)cc1`
  * 生成命中：`Cc1ccc(S(=O)(=O)O)cc1`
  * 记录产物：`Cc1ccc(S(=O)(=O)O)cc1`
* `ord-459b22e82b8f4decbddb6d75a4854f6b`
  * 反应物：`O + O=N[O-].[Na+] + O=S(=O)(O[C@H]1CO[C@@H](OCc2ccccc2)[C@@H](OCc2ccccc2)[C@@H]1OCc1ccccc1)C(F)(F)F`
  * 生成命中：`OC1COC(OCc2ccccc2)C(OCc2ccccc2)C1OCc1ccccc1`
  * 记录产物：`OC1COC(OCc2ccccc2)C(OCc2ccccc2)C1OCc1ccccc1`

### `hydrolysis_phosphate_001` 磷酸酯水解

* `ord-b76832d8c2fe47609a139e614967c486`
  * 反应物：`CCOP(=O)(CCC(C)=CCc1c(O)c2c(c(C)c1OC)COC2=O)OCC + CO + Cl + [Li+].[OH-]`
  * 生成命中：`CCOP(=O)(O)CCC(C)=CCc1c(O)c2c(c(C)c1OC)COC2=O`
  * 记录产物：`CCOP(=O)(O)CCC(C)=CCc1c(O)c2c(c(C)c1OC)COC2=O`
* `ord-7c3ae6450c7a42018e55542fd2ea202a`
  * 反应物：`CCCCN(CCCC)CCCC + CCCC[NH+](CCCC)CCCC + O=C([O-])O.[NH4+] + O=P([O-])([O-])OP(=O)([O-])OP(=O)([O-])OP(=O)(O)O.O=c1ccn([C@@H]2O[C@H](CO)[C@@H](O)[C@H]2O)c(=O)[nH]1.O=c1ccn([C@@H]2O[C@H](CO)[C@@H](O)[C@H]2O)c(=O)[nH]1.[Na+].[Na+].[Na+].[Na+]`
  * 生成命中：`O=c1ccn(C2OC(CO)C(O)C2O)c(=O)[nH]1`
  * 记录产物：`O=P(O)(O)OP(=O)(O)OP(=O)(O)OP(=O)(O)O ; O=P(O)(O)OP(=O)(O)OP(=O)(O)OP(=O)(O)O.O=c1ccn(C2OC(CO)C(O)C2O)c(=O)[nH]1.O=c1ccn(C2OC(CO)C(O)C2O)c(=O)[nH]1 ; O=c1ccn(C2OC(CO)C(O)C2O)c(=O)[nH]1`
* `ord-86616bee0271413c96e01ad81a58aacd`
  * 反应物：`CCOP(=O)(Cc1ccc(Nc2ncc(C(F)(F)F)c(Nc3ccc(-c4cnn(C[C@H](O)CO)c4)c4c3C(=O)N(C)C4)n2)c(OC)c1)OCC + CCOP(=O)(O)Cc1ccc(Nc2ncc(C(F)(F)F)c(Nc3ccc(-c4cnn(CCCO)c4)cc3C(=O)N(CC)CC)n2)c(OC)c1`
  * 生成命中：`CCOP(=O)(O)Cc1ccc(Nc2ncc(C(F)(F)F)c(Nc3ccc(-c4cnn(CC(O)CO)c4)c4c3C(=O)N(C)C4)n2)c(OC)c1`
  * 记录产物：`CCOP(=O)(O)Cc1ccc(Nc2ncc(C(F)(F)F)c(Nc3ccc(-c4cnn(CC(O)CO)c4)c4c3C(=O)N(C)C4)n2)c(OC)c1`

### `hydrolysis_acetal_001` 缩醛水解

* `ord-991308a13d764cc0817ac696051b408e`
  * 反应物：`CC(C)(C)[Si](Cl)(c1ccccc1)c1ccccc1 + CC(C)(C)[Si](OCc1ccc(CCCC2OCCO2)cc1)(c1ccccc1)c1ccccc1 + Cl + O=C([O-])[O-].[K+].[K+]`
  * 生成命中：`CC(C)(C)[Si](OCc1ccc(CCCC=O)cc1)(c1ccccc1)c1ccccc1`
  * 记录产物：`CC(C)(C)[Si](OCc1ccc(CCCC=O)cc1)(c1ccccc1)c1ccccc1`
* `ord-71ad9a67baf44ed6bce3a9333c8c2b29`
  * 反应物：`Cl + O=C([O-])[O-].[K+].[K+] + c1c(COC2CCCCO2)noc1CN1CCOCC1`
  * 生成命中：`OCc1cc(CN2CCOCC2)on1`
  * 记录产物：`OCc1cc(CN2CCOCC2)on1`
* `ord-2603c295c6774fb2b21832e07be7eeeb`
  * 反应物：`Cc1ccc(S(=O)(=O)O)cc1 + c1c(C2OCCO2)sc2c1OCCC2`
  * 生成命中：`O=Cc1cc2c(s1)CCCO2`
  * 记录产物：`O=Cc1cc2c(s1)CCCO2`

### `hydrolysis_hemiacetal_001` 半缩醛水解

* `ord-26bde17dc5b64039ae34d2762669f729`
  * 反应物：`CC(O)Oc1nnc(Cl)cc1N1CCNCC1.O=C(O)/C=C/C(=O)O`
  * 生成命中：`Oc1nnc(Cl)cc1N1CCNCC1`
  * 记录产物：`Oc1nnc(Cl)cc1N1CCNCC1`

### `oxidation_hydroxyl_001` 羟基氧化

* `ord-518a16e34f3943a5b14400a699394dc9`
  * 反应物：`CC(C)=O.O=S(=O)(O)O.[O]=[Cr](=[O])=[O] + CCCCCCCCCCCC1CC(O)[C@@H](CCCCCC)C(=O)O1 + O`
  * 生成命中：`CCCCCCCCCCCC1CC(=O)C(CCCCCC)C(=O)O1`
  * 记录产物：`CCCCCCCCCCCC1CC(=O)C(CCCCCC)C(=O)O1`
* `ord-9d59393c4c9049a0808495226bbc11b0`
  * 反应物：`CC(=O)OI1(OC(C)=O)(OC(C)=O)OC(=O)c2ccccc21 + COC(=O)N(Cc1cc(C(F)(F)F)cc(C(F)(F)F)c1)Cc1cc(C(F)(F)F)ccc1-c1cc(C(O)C(F)(F)F)ccc1OC`
  * 生成命中：`COC(=O)N(Cc1cc(C(F)(F)F)cc(C(F)(F)F)c1)Cc1cc(C(F)(F)F)ccc1-c1cc(C(=O)C(F)(F)F)ccc1OC`
  * 记录产物：`COC(=O)N(Cc1cc(C(F)(F)F)cc(C(F)(F)F)c1)Cc1cc(C(F)(F)F)ccc1-c1cc(C(=O)C(F)(F)F)ccc1OC`
* `ord-1041ebbad9184896b84294f5baa9ee66`
  * 反应物：`CCN(CC)CC + COC(=O)c1ccc([C@H](c2ccc(Cl)cc2)N2CC(O)C2)cc1 + CS(C)=O + O=C(Cl)C(=O)Cl`
  * 生成命中：`COC(=O)c1ccc(C(c2ccc(Cl)cc2)N2CC(=O)C2)cc1`
  * 记录产物：`COC(=O)c1ccc(C(c2ccc(Cl)cc2)N2CC(=O)C2)cc1`

### `oxidation_aldehyde_001` 醛氧化

* `ord-3241ab6c22d447b498b7ce647cbfc9d9`
  * 反应物：`CC(=O)O + O=Cc1ccc(C(=O)OCc2ccccc2)cc1`
  * 生成命中：`O=C(O)c1ccc(C(=O)OCc2ccccc2)cc1`
  * 记录产物：`O=C(O)c1ccc(C(=O)OCc2ccccc2)cc1`
* `ord-3cf88f8f01ae4eda9158f1af5217637a`
  * 反应物：`CC(C)(C)[O][K].CN(C)C=O.FC(F)F + O=Cc1ccccc1`
  * 生成命中：`O=C(O)c1ccccc1`
  * 记录产物：`O=C(O)c1ccccc1 ; OCc1ccccc1`
* `ord-190dcd50c65c412eb9c6458f3623a7b2`
  * 反应物：`CC(C)=O.O=S(=O)(O)O.[O]=[Cr](=[O])=[O] + COC(=O)C1(CCCC=O)CCN(C(=O)OC(C)(C)C)CC1`
  * 生成命中：`COC(=O)C1(CCCC(=O)O)CCN(C(=O)OC(C)(C)C)CC1`
  * 记录产物：`COC(=O)C1(CCCC(=O)O)CCN(C(=O)OC(C)(C)C)CC1`

### `oxidation_amine_001` 胺氧化

* `ord-4f7a9ea9dccc4c679c1789f679ee250a`
  * 反应物：`CCCCN=C=O + NCCN`
  * 生成命中：`N`
  * 记录产物：`CCCCNC(=O)NCCN ; N`
* `ord-c8c81d7d5d624a72ba91d08d0c646eb0`
  * 反应物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 + CN(C)CCN`
  * 生成命中：`N`
  * 记录产物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 ; N`
* `ord-8e738d085e454a4eaf1163de4a12dd9d`
  * 反应物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 + CN(C)CCN`
  * 生成命中：`N`
  * 记录产物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 ; N`

### `reduction_ketone_001` 酮还原

* `ord-59ad5f10a39944bab640d9fbd6671548`
  * 反应物：`O=C1CCC(c2ccccc2)CC1 + [BH4-].[Na+]`
  * 生成命中：`OC1CCC(c2ccccc2)CC1`
  * 记录产物：`OC1CCC(c2ccccc2)CC1`
* `ord-4213d05daadd4cc1a427b80287607a1d`
  * 反应物：`CC(C)(C)[Si](C)(C)OC1C=CC(=O)C1 + COC(C)(C)C + [Al+3].[H-].[H-].[H-].[H-].[Li+] + [Br-].[Br-].[Mg+2]`
  * 生成命中：`CC(C)(C)[Si](C)(C)OC1C=CC(O)C1`
  * 记录产物：`CC(C)(C)[Si](C)(C)OC1C=CC(O)C1`
* `ord-40b377d619b3445095890b35e71e45d2`
  * 反应物：`CC(=O)OC1CC[C@@]2(C)C(=CC[C@@H]3[C@@H]2CC[C@]2(C)C(=O)CC[C@@H]32)C1 + [BH4-].[Na+]`
  * 生成命中：`CC(=O)OC1CCC2(C)C(=CCC3C2CCC2(C)C(O)CCC32)C1`
  * 记录产物：`CC(=O)OC1CCC2(C)C(=CCC3C2CCC2(C)C(O)CCC32)C1`

### `demethylation_aromatic_001` 脱甲基

* `ord-c366215603d74e8f80c204c070b5fd26`
  * 反应物：`CCS + CO + COc1ccc2c(C(=O)c3ccc(OCCN4CCCCC4)cc3)c(-c3ccc4ccccc4c3)sc2c1 + [Al+3].[Cl-].[Cl-].[Cl-]`
  * 生成命中：`O=C(c1ccc(OCCN2CCCCC2)cc1)c1c(-c2ccc3ccccc3c2)sc2cc(O)ccc12`
  * 记录产物：`O=C(c1ccc(OCCN2CCCCC2)cc1)c1c(-c2ccc3ccccc3c2)sc2cc(O)ccc12`
* `ord-9f122af1a0394a17b79d34afbf18a558`
  * 反应物：`COc1ccc(N2CCN(c3ccncc3)CC2)cc1 + N + O`
  * 生成命中：`Oc1ccc(N2CCN(c3ccncc3)CC2)cc1`
  * 记录产物：`Oc1ccc(N2CCN(c3ccncc3)CC2)cc1`
* `ord-afe5cbc25fd340cf8536ac9ee64ce538`
  * 反应物：`BrB(Br)Br + COc1cccc(N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)C(=O)c2ccc(NC(C)=O)cc2)c1 + O=C([O-])O.[Na+]`
  * 生成命中：`CC(=O)Nc1ccc(C(=O)N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)c2cccc(O)c2)cc1`
  * 记录产物：`CC(=O)Nc1ccc(C(=O)N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)c2cccc(O)c2)cc1`

### `decarboxylation_aromatic_001` 芳香酸脱羧

* `ord-a6d16c84992d44c5ba2388e74f39994d`
  * 反应物：`O=C(O)c1cc(-c2ccncc2)c(-c2ccc(F)cc2)s1 + c1ccc2ncccc2c1`
  * 生成命中：`Fc1ccc(-c2sccc2-c2ccncc2)cc1`
  * 记录产物：`Fc1ccc(-c2sccc2-c2ccncc2)cc1`
* `ord-db23a7df47ce43e88181e32cd36573c0`
  * 反应物：`Cc1ccc2c(n1)sc1c(O)c(C(=O)O)nnc12`
  * 生成命中：`Cc1ccc2c(n1)sc1c(O)cnnc12`
  * 记录产物：`Cc1ccc2c(n1)sc1c(O)cnnc12`
* `ord-e9551f53bc29421fa7d1f8c4aefb21cf`
  * 反应物：`CCc1[nH]c(=O)[nH]c1C(=O)O + O=C(O)c1ccc(-n2ccnc2)cc1`
  * 生成命中：`O=C=O`
  * 记录产物：`CCc1[nH]c(=O)[nH]c1C(=O)c1ccc(-n2ccnc2)cc1 ; O=C=O`

### `decarboxylation_beta_keto_001` β-酮酸脱羧

* `ord-3106a99bd54c4b21ada04ba10d9f7f30`
  * 反应物：`CCN(CC)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC1NN(c2ccc(OC)cc2)C(=O)C1=O + COC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O`
  * 生成命中：`COc1ccc(N2NCC(=O)C2=O)cc1`
  * 记录产物：`COc1ccc(N2NCC(=O)C2=O)cc1`
* `ord-9d80b20dec5a45708345ce38f4ea4e7e`
  * 反应物：`CC(CCCCCC1=CCCC1=O)(C(=O)O)C(=O)O.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + CCOC(=O)C(C)(CCCCCC1=CCCC1=O)C(=O)OCC.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + [K+].[OH-]`
  * 生成命中：`CC(CCCCCC1=CCCC1=O)C(=O)O`
  * 记录产物：`CC(CCCCCC1=CCCC1=O)C(=O)O ; CC(CCCCCC1=CCCC1=O)C(=O)O.ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1.[Br-].[Br-] ; ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1 ; [Br-]`
* `ord-31c3e2e98cd44467899f028d14290818`
  * 反应物：`O=C(O)C1(C(=O)O)CC2(CCC2)C1`
  * 生成命中：`O=C(O)C1CC2(CCC2)C1`
  * 记录产物：`O=C(O)C1CC2(CCC2)C1`

### `hydroxylation_aromatic_001` 芳香环羟基化

* `ord-49d570f5b6da402d8ae3be1663819276`
  * 反应物：`COc1ccc2c(Nc3c(Cl)cncc3Cl)cc(=O)oc2c1OC1CCCC1 + NC(N)=O.OO + O=C(OC(=O)C(F)(F)F)C(F)(F)F + O=S([O-])([O-])=S.[Na+].[Na+]`
  * 生成命中：`COc1ccc2c(Nc3c(Cl)cncc3Cl)c(O)c(=O)oc2c1OC1CCCC1`
  * 记录产物：`COc1ccc2c(Nc3c(Cl)cncc3Cl)c(O)c(=O)oc2c1OC1CCCC1`
* `ord-01f2f8a8a53d4d1d8fa1d6c058f5497a`
  * 反应物：`CCOP(=S)(S)OCC + N#Cc1c(O)cccc1O + NC(=S)c1ccccc1O`
  * 生成命中：`NC(=S)c1c(O)cccc1O`
  * 记录产物：`NC(=S)c1c(O)cccc1O`
* `ord-e7b420fca4cd44b99f56ad6c52a98cc7`
  * 反应物：`CC1(C)OB(B2OC(C)(C)C(C)(C)O2)OC1(C)C + Clc1cccc(Br)c1 + O=S([O-])OO.[K+]`
  * 生成命中：`Oc1cc(Cl)cc(Br)c1`
  * 记录产物：`Oc1cc(Cl)cc(Br)c1`

### `hydration_alkene_001` 烯烃水合

* `ord-b8c3fa2dbf1b481391b010440c8960b9`
  * 反应物：`C=CCCC[C@@H](O)c1ccc(-c2ccc(Cl)cc2Cl)cc1 + CCOCC.FB(F)F + O=C([O-])[O-].[K+].[K+] + OO`
  * 生成命中：`OCCCCCC(O)c1ccc(-c2ccc(Cl)cc2Cl)cc1`
  * 记录产物：`OCCCCCC(O)c1ccc(-c2ccc(Cl)cc2Cl)cc1`
* `ord-2b11fcbc50ca4a2bb72a4e6681ad232d`
  * 反应物：`C=CC(=C)C + CC(=O)O`
  * 生成命中：`C=CC(C)(C)O`
  * 记录产物：`C=CC(C)(C)O ; CC(C)=CCCC(=O)[O-] ; CC(C)=CCO`
* `ord-32dd13615e9c4b979158fca19b892678`
  * 反应物：`B.C1CCOC1 + CC(C)(C)OC(=O)NC1CC=CC1 + OO + [Na+].[OH-]`
  * 生成命中：`CC(C)(C)OC(=O)NC1CCC(O)C1`
  * 记录产物：`CC(C)(C)OC(=O)NC1CCC(O)C1`

### `hydration_enone_001` α,β-不饱和羰基水合

* `ord-6b5f322ea8cd4872a6831d2085442628`
  * 反应物：`C=CCO + CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H]1CC=CC(=O)O1 + Cl + [Li+].[OH-]`
  * 生成命中：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`
  * 记录产物：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`
* `ord-7150ca15c2424185a1b442fbafb5d959`
  * 反应物：`C=CCO + CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H]1CC=CC(=O)O1 + Cl + [Li+].[OH-]`
  * 生成命中：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`
  * 记录产物：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`
* `ord-48cf58e1338847e8a70ffcf248a106d7`
  * 反应物：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H]1CC=CC(=O)O1 + Cl + O=S(=O)(O)O + OCc1ccccc1`
  * 生成命中：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`
  * 记录产物：`CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CCC1CC(O)CC(=O)O1`

### `esterification_delta_lactone_001` δ-内酯化

* `ord-87b35a6264bb4aac9c89aeef80b41113`
  * 反应物：`C(=NC1CCCCC1)=NC1CCCCC1 + CC[C@H](C)C(=O)O[C@H]1C[C@H](O)C=C2C=C[C@H](C)[C@H](CC[C@@H](O)C[C@@H](O)CC(=O)O)[C@H]21 + O=C1CCC(=O)N1O`
  * 生成命中：`CCC(C)C(=O)OC1CC(O)C=C2C=CC(C)C(CCC3CC(O)CC(=O)O3)C21`
  * 记录产物：`CCC(C)C(=O)OC1CC(O)C=C2C=CC(C)C(CCC3CC(O)CC(=O)O3)C21`

### `oxidation_primary_alcohol_001` 伯醇氧化成醛

* `ord-8547a040ad9a425c98f22d4b4c6c403c`
  * 反应物：`CC(C)Nc1ccccc1CO + N#CC1=C(C#N)C(=O)C(Cl)=C(Cl)C1=O`
  * 生成命中：`CC(C)Nc1ccccc1C=O`
  * 记录产物：`CC(C)Nc1ccccc1C=O`
* `ord-2dd48e91d9f149d4ba76a652ed59e760`
  * 反应物：`CCN(CC)CC + O + OCc1cn(C(c2ccccc2)(c2ccccc2)c2ccccc2)cn1`
  * 生成命中：`O=Cc1cn(C(c2ccccc2)(c2ccccc2)c2ccccc2)cn1`
  * 记录产物：`O=Cc1cn(C(c2ccccc2)(c2ccccc2)c2ccccc2)cn1`
* `ord-42e2736d1d544ffaa239652e6a28183b`
  * 反应物：`CC(C)(C)OC(=O)N(Cc1ccc(CO)cc1)Cc1ncccc1O`
  * 生成命中：`CC(C)(C)OC(=O)N(Cc1ccc(C=O)cc1)Cc1ncccc1O`
  * 记录产物：`CC(C)(C)OC(=O)N(Cc1ccc(C=O)cc1)Cc1ncccc1O`

### `oxidation_sulfide_001` 硫醚氧化成亚砜

* `ord-0390e1237c0d4ce1b863fbe6e79e9218`
  * 反应物：`CCOCCSC(SC(C)=O)=C(C(=O)OCc1ccc([N+](=O)[O-])cc1)N1C(=O)CC1SCC + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CCOCCSC(SC(C)=O)=C(C(=O)OCc1ccc([N+](=O)[O-])cc1)N1C(=O)CC1S(=O)CC`
  * 记录产物：`CCOCCSC(SC(C)=O)=C(C(=O)OCc1ccc([N+](=O)[O-])cc1)N1C(=O)CC1S(=O)CC`
* `ord-2ebc34d91ba745a7a7dd4bc687e432b0`
  * 反应物：`Cc1ccc(-c2c[nH]nc2C(F)(F)F)cc1SCC(F)(F)F + O=C(OO)c1cccc(Cl)c1 + O=S([O-])[O-].[Na+].[Na+]`
  * 生成命中：`Cc1ccc(-c2c[nH]nc2C(F)(F)F)cc1S(=O)CC(F)(F)F`
  * 记录产物：`Cc1ccc(-c2c[nH]nc2C(F)(F)F)cc1S(=O)CC(F)(F)F`
* `ord-a31a8aea26db44ba9a6c67dae080060b`
  * 反应物：`CSc1nnc2n1C=Cc1ccccc1C2 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CS(=O)c1nnc2n1C=Cc1ccccc1C2`
  * 记录产物：`CS(=O)c1nnc2n1C=Cc1ccccc1C2`

### `oxidation_epoxide_001` 双键环氧化

* `ord-07e7b8d911554e5d89dde51561daed3a`
  * 反应物：`C1=CCCCCCC1 + ClC(Cl)Cl + O=C(CCl)C(Cl)(Cl)Cl + OO`
  * 生成命中：`C1CCCC2OC2CC1`
  * 记录产物：`C1CCCC2OC2CC1`
* `ord-94f84cbc479e491e8ede2b5a145fa82a`
  * 反应物：`CC1CCC=CCN1C(=O)OCc1ccccc1 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC1CCC2OC2CN1C(=O)OCc1ccccc1`
  * 记录产物：`CC1CCC2OC2CN1C(=O)OCc1ccccc1`
* `ord-2b7ec160332042a69b0aac988bc41c04`
  * 反应物：`C[C@]12CC=CC[C@@H]1CC[C@@H]1[C@@H]2CC[C@]2(C)C(=O)CC[C@@H]12 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC12CCC3C(CCC4CC5OC5CC43C)C1CCC2=O`
  * 记录产物：`CC12CCC3C(CCC4CC5OC5CC43C)C1CCC2=O`

### `oxidation_dehydrogenation_enone_001` 脱氢成α,β-不饱和羰基

* `ord-722cf82db39c409eb44cd3dedcb941d6`
  * 反应物：`CCOC(=O)C1CN=C(CN2C(=O)c3ccccc3C2=O)c2c(OC)cc(OC)cc21 + O`
  * 生成命中：`CCOC(=O)c1cnc(CN2C(=O)c3ccccc3C2=O)c2c(OC)cc(OC)cc12`
  * 记录产物：`CCOC(=O)c1cnc(CN2C(=O)c3ccccc3C2=O)c2c(OC)cc(OC)cc12`
* `ord-23aebc49575048f78dc97f67179657f2`
  * 反应物：`CC1CC(=O)NN=C1c1ccc2c(c1)CCC(=O)N2C + N#CC1=C(C#N)C(=O)C(Cl)=C(Cl)C1=O`
  * 生成命中：`CC1CC(=O)NN=C1c1ccc2c(ccc(=O)n2C)c1`
  * 记录产物：`CC1CC(=O)NN=C1c1ccc2c(ccc(=O)n2C)c1`
* `ord-4a59ea2658314cef9afdbdd4505f8643`
  * 反应物：`BrBr + CC1CC(=O)NN=C1c1ccc(Br)cc1`
  * 生成命中：`Cc1cc(=O)[nH]nc1-c1ccc(Br)cc1`
  * 记录产物：`Cc1cc(=O)[nH]nc1-c1ccc(Br)cc1`

### `reduction_aldehyde_001` 醛还原成醇

* `ord-c63ace3342d84bbd8c5c2007a1065d40`
  * 反应物：`O=Cc1cc2ccccc2nc1I`
  * 生成命中：`OCc1cc2ccccc2nc1I`
  * 记录产物：`OCc1cc2ccccc2nc1I`
* `ord-621039449c2a4a8292dc2cf8bcf28ed2`
  * 反应物：`O + O=Cc1ccc(C2CC2)cc1 + [BH4-].[Li+]`
  * 生成命中：`OCc1ccc(C2CC2)cc1`
  * 记录产物：`OCc1ccc(C2CC2)cc1`
* `ord-8f16daff33a54d7dbea2b1c031fe1318`
  * 反应物：`COc1ccc(C=O)c(Cl)c1 + [BH4-].[Na+]`
  * 生成命中：`COc1ccc(CO)c(Cl)c1`
  * 记录产物：`COc1ccc(CO)c(Cl)c1`

### `reduction_alkene_001` 双键加氢

* `ord-a2fcb8e364ca4dd2ada72db56fde3611`
  * 反应物：`CC(C)N1C(=O)[C@@H](C/C=C/C(=O)O)O[C@H](c2ccccc2Cl)c2cc(Cl)ccc21 + [H][H]`
  * 生成命中：`CC(C)N1C(=O)C(CCCC(=O)O)OC(c2ccccc2Cl)c2cc(Cl)ccc21`
  * 记录产物：`CC(C)N1C(=O)C(CCCC(=O)O)OC(c2ccccc2Cl)c2cc(Cl)ccc21`
* `ord-44d7775ce6aa4fefbef4fb0336de5ad9`
  * 反应物：`O=C(CCCCCCCC=Cc1ccc(Cl)cc1)C1=C(O)COC1=O + [H][H]`
  * 生成命中：`O=C(CCCCCCCCCc1ccc(Cl)cc1)C1=C(O)COC1=O`
  * 记录产物：`O=C(CCCCCCCCCc1ccc(Cl)cc1)C1=C(O)COC1=O`
* `ord-8ba885339f8d41249dc7afe4b839d218`
  * 反应物：`O=[N+]([O-])C=Cc1cccc(Cl)c1 + [BH4-].[Na+]`
  * 生成命中：`O=[N+]([O-])CCc1cccc(Cl)c1`
  * 记录产物：`O=[N+]([O-])CCc1cccc(Cl)c1`

### `hydrolysis_lactam_001` 内酰胺开环

* `ord-b5c1249063ad41ecb9a886e640b8e144`
  * 反应物：`CC(C)(C)OC(=O)N1CCN(c2ccc3oc(C(N)=O)cc3c2)CC1`
  * 生成命中：`NC(=O)c1cc2cc(N3CCNCC3)ccc2o1`
  * 记录产物：`NC(=O)c1cc2cc(N3CCNCC3)ccc2o1`
* `ord-65e718a8f3934e1487660a0d4b652d2f`
  * 反应物：`C=CCOC(=O)[C@@H](CCc1ccccc1)NC(=O)OC(C)(C)C + COc1ccccc1 + O=C(O)C(F)(F)F + O=C([O-])O.[Na+]`
  * 生成命中：`C=CCOC(=O)C(N)CCc1ccccc1`
  * 记录产物：`C=CCOC(=O)C(N)CCc1ccccc1`
* `ord-83875325c1ee4a0ea07fd297824b70f1`
  * 反应物：`CN1c2ccccc2C(c2ccccc2F)=NCC1CNC(=O)C(Cc1c[nH]c2ccccc12)NC(=O)OC(C)(C)C + Cl`
  * 生成命中：`CN1c2ccccc2C(c2ccccc2F)=NCC1CNC(=O)C(N)Cc1c[nH]c2ccccc12`
  * 记录产物：`CN1c2ccccc2C(c2ccccc2F)=NCC1CNC(=O)C(N)Cc1c[nH]c2ccccc12 ; CN1c2ccccc2C(c2ccccc2F)=NCC1CNC(=O)C(N)Cc1c[nH]c2ccccc12.CN1c2ccccc2C(c2ccccc2F)=NCC1CNC(=O)C(N)Cc1c[nH]c2ccccc12.Cl.Cl.Cl.Cl.O.O.O ; Cl ; O`

### `hydrolysis_imine_001` 亚胺水解

* `ord-b1dcbef1739948fe87cc9c46b0f68caa`
  * 反应物：`C1CCOC1 + COc1cc(C=NC(C(C)C)C(C)C)c(C(C)C)cc1OC + Cl`
  * 生成命中：`COc1cc(C=O)c(C(C)C)cc1OC`
  * 记录产物：`COc1cc(C=O)c(C(C)C)cc1OC`
* `ord-7aa29bacc222422f86399fac0c0d4e76`
  * 反应物：`CCOC(C)=O + COc1ccc(C=NC(c2ccc(Cl)nc2)(c2ccc3c(c2)c(-c2cccc(Cl)c2)cc(=O)n3CC2CC2)c2cncn2C)cc1 + Cl + O=C([O-])[O-].[K+].[K+]`
  * 生成命中：`Cn1cncc1C(N)(c1ccc(Cl)nc1)c1ccc2c(c1)c(-c1cccc(Cl)c1)cc(=O)n2CC1CC1`
  * 记录产物：`Cn1cncc1C(N)(c1ccc(Cl)nc1)c1ccc2c(c1)c(-c1cccc(Cl)c1)cc(=O)n2CC1CC1`
* `ord-2e0fa9313051494aba91e78764bf09e3`
  * 反应物：`CC(C)CN=Cc1cccc(Oc2ccccc2)c1 + Cl + O`
  * 生成命中：`O=Cc1cccc(Oc2ccccc2)c1`
  * 记录产物：`O=Cc1cccc(Oc2ccccc2)c1`

### `cyclization_lactam_001` 分子内酰胺化

* `ord-b80adfa3516a434db141f13b4adac7f3`
  * 反应物：`CC(C)[C@H](N)C(=O)O + CC[C@H](C)[C@H](N)C(=O)O + N[C@@H](CCC(=O)O)C(=O)O + N[C@@H](Cc1ccc(O)cc1)C(=O)O`
  * 生成命中：`O`
  * 记录产物：`CC(=O)O ; CC(=O)O.CCCCO.O.c1ccncc1 ; CCCCO ; O ; c1ccncc1`
* `ord-d288bf917f0b4bd4840f67269f252b57`
  * 反应物：`CC(C)(C)OC(=O)[C@@H]1CC(CN)(CC(=O)O)CN1C(=O)OC(C)(C)C + CCN(C(C)C)C(C)C + CCN=C=NCCCN(C)C.Cl + On1nnc2ccccc21`
  * 生成命中：`CC(C)(C)OC(=O)C1CC2(CNC(=O)C2)CN1C(=O)OC(C)(C)C`
  * 记录产物：`CC(C)(C)OC(=O)C1CC2(CNC(=O)C2)CN1C(=O)OC(C)(C)C`

### `cyclization_ether_001` 分子内脱水成醚

* `ord-a5fb5c3cc7cf4d64ad4d21d86b8e6e50`
  * 反应物：`CC(C)OC(=O)/N=N/C(=O)OC(C)C + CC1(CO)CC[C@](O)(C(=O)O)C1(C)C + c1ccc(P(c2ccccc2)c2ccccc2)cc1`
  * 生成命中：`CC12CCC(C(=O)O)(OC1)C2(C)C`
  * 记录产物：`CC12CCC(C(=O)O)(OC1)C2(C)C`
* `ord-3e81f2c249494cdc8752073e4470ad61`
  * 反应物：`CC(C)(C)[Si](Oc1cccc(CC(CCO)C(O)c2nc(-c3ccccc3)c(-c3ccccc3)o2)c1)(c1ccccc1)c1ccccc1 + Cc1ccc(S(=O)(=O)O)cc1`
  * 生成命中：`CC(C)(C)[Si](Oc1cccc(CC2CCOC2c2nc(-c3ccccc3)c(-c3ccccc3)o2)c1)(c1ccccc1)c1ccccc1`
  * 记录产物：`CC(C)(C)[Si](Oc1cccc(CC2CCOC2c2nc(-c3ccccc3)c(-c3ccccc3)o2)c1)(c1ccccc1)c1ccccc1`
* `ord-ebe7fdf5beaa48b0a4e162141f7df727`
  * 反应物：`CCCc1c(Cc2ccc(-c3ccccc3C#N)cc2)c(=O)n([C@H]2CC[C@H](OCC(O)CCCO)CC2)c2ncnn12 + CCOC(=O)N=NC(=O)OCC + O + c1ccc(P(c2ccccc2)c2ccccc2)cc1`
  * 生成命中：`CCCc1c(Cc2ccc(-c3ccccc3C#N)cc2)c(=O)n(C2CCC(OCC3CCCO3)CC2)c2ncnn12`
  * 记录产物：`CCCc1c(Cc2ccc(-c3ccccc3C#N)cc2)c(=O)n(C2CCC(OCC3CCCO3)CC2)c2ncnn12`

### `cyclization_lactone_delta_001` δ-羟基酸内酯化(备用)

* `ord-87b35a6264bb4aac9c89aeef80b41113`
  * 反应物：`C(=NC1CCCCC1)=NC1CCCCC1 + CC[C@H](C)C(=O)O[C@H]1C[C@H](O)C=C2C=C[C@H](C)[C@H](CC[C@@H](O)C[C@@H](O)CC(=O)O)[C@H]21 + O=C1CCC(=O)N1O`
  * 生成命中：`CCC(C)C(=O)OC1CC(O)C=C2C=CC(C)C(CCC3CC(O)CC(=O)O3)C21`
  * 记录产物：`CCC(C)C(=O)OC1CC(O)C=C2C=CC(C)C(CCC3CC(O)CC(=O)O3)C21`

### `isomerization_double_bond_001` 双键位置异构

* `ord-4d2a5ce25ca84394ba1e3974ebce74f6`
  * 反应物：`C=C + C=CC + CC=C1CC2=CCC1C2 + Fc1c(F)c(F)c(B(c2c(F)c(F)c(F)c(F)c2F)c2c(F)c(F)c(F)c(F)c2F)c(F)c1F`
  * 生成命中：`CC=C1CC2C=CC1C2`
  * 记录产物：`C=C ; C=C.C=CC.CC=C1CC2C=CC1C2 ; C=CC ; CC=C1CC2C=CC1C2`
* `ord-41eba227707c4a7fb38c30d845e22448`
  * 反应物：`C1=CCOC1 + C1CCOC1 + O`
  * 生成命中：`C1=COCC1`
  * 记录产物：`C1=COCC1 ; O=C1CCCO1 ; O=CCCCO ; c1ccoc1`
* `ord-71a351736a0348eb8442aa7d42da8f29`
  * 反应物：`C=C(C)CCC(=O)OCC + CCOC(=O)C=CC(C)C + CCOC(=O)CC=C(C)C`
  * 生成命中：`CCOC(=O)C=CC(C)C`
  * 记录产物：`CCOC(=O)C=CC(C)C`

### `rearrangement_retro_aldol_001` 逆羟醛裂解

* `ord-3106a99bd54c4b21ada04ba10d9f7f30`
  * 反应物：`CCN(CC)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC1NN(c2ccc(OC)cc2)C(=O)C1=O + COC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O`
  * 生成命中：`COc1ccc(N2NCC(=O)C2=O)cc1`
  * 记录产物：`COc1ccc(N2NCC(=O)C2=O)cc1`
* `ord-9d80b20dec5a45708345ce38f4ea4e7e`
  * 反应物：`CC(CCCCCC1=CCCC1=O)(C(=O)O)C(=O)O.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + CCOC(=O)C(C)(CCCCCC1=CCCC1=O)C(=O)OCC.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + [K+].[OH-]`
  * 生成命中：`CC(CCCCCC1=CCCC1=O)C(=O)O`
  * 记录产物：`CC(CCCCCC1=CCCC1=O)C(=O)O ; CC(CCCCCC1=CCCC1=O)C(=O)O.ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1.[Br-].[Br-] ; ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1 ; [Br-]`
* `ord-31c3e2e98cd44467899f028d14290818`
  * 反应物：`O=C(O)C1(C(=O)O)CC2(CCC2)C1`
  * 生成命中：`O=C(O)C1CC2(CCC2)C1`
  * 记录产物：`O=C(O)C1CC2(CCC2)C1`

### `decarboxylation_malonic_001` 丙二酸型脱羧

* `ord-3106a99bd54c4b21ada04ba10d9f7f30`
  * 反应物：`CCN(CC)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O + CCOC1NN(c2ccc(OC)cc2)C(=O)C1=O + COC(=O)C1NN(c2ccc(OC)cc2)C(=O)C1=O`
  * 生成命中：`COc1ccc(N2NCC(=O)C2=O)cc1`
  * 记录产物：`COc1ccc(N2NCC(=O)C2=O)cc1`
* `ord-9d80b20dec5a45708345ce38f4ea4e7e`
  * 反应物：`CC(CCCCCC1=CCCC1=O)(C(=O)O)C(=O)O.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + CCOC(=O)C(C)(CCCCCC1=CCCC1=O)C(=O)OCC.O/N=C/c1cc[n+](C[n+]2ccc(/C=N/O)cc2)cc1.[Br-].[Br-] + [K+].[OH-]`
  * 生成命中：`CC(CCCCCC1=CCCC1=O)C(=O)O`
  * 记录产物：`CC(CCCCCC1=CCCC1=O)C(=O)O ; CC(CCCCCC1=CCCC1=O)C(=O)O.ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1.[Br-].[Br-] ; ON=Cc1cc[n+](C[n+]2ccc(C=NO)cc2)cc1 ; [Br-]`
* `ord-31c3e2e98cd44467899f028d14290818`
  * 反应物：`O=C(O)C1(C(=O)O)CC2(CCC2)C1`
  * 生成命中：`O=C(O)C1CC2(CCC2)C1`
  * 记录产物：`O=C(O)C1CC2(CCC2)C1`

### `elimination_deamination_001` 氧化脱氨成羰基

* `ord-4f7a9ea9dccc4c679c1789f679ee250a`
  * 反应物：`CCCCN=C=O + NCCN`
  * 生成命中：`N`
  * 记录产物：`CCCCNC(=O)NCCN ; N`
* `ord-c8c81d7d5d624a72ba91d08d0c646eb0`
  * 反应物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 + CN(C)CCN`
  * 生成命中：`N`
  * 记录产物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 ; N`
* `ord-8e738d085e454a4eaf1163de4a12dd9d`
  * 反应物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 + CN(C)CCN`
  * 生成命中：`N`
  * 记录产物：`CCC(Br)c1nc2ccccc2c(=O)n1Cc1ccccc1 ; N`

### `esterification_transesterification_001` 酯交换

* `ord-00533d2621284180b8d6e372c9496cb7`
  * 反应物：`CC(=O)OC(C)=O + CCOC(C)=O + CN(C)c1ccccn1 + O[C@@H]1C=C[C@H](OC2CCCCO2)C1`
  * 生成命中：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
  * 记录产物：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
* `ord-51ef9f6ae2d14a58b7d97c8023ad50fd`
  * 反应物：`CC(=O)OC(C)=O + CCOC(=O)CC(O)c1ccc(C)nc1 + [Na+].[OH-] + c1ccncc1`
  * 生成命中：`CCOC(=O)CC(OC(C)=O)c1ccc(C)nc1`
  * 记录产物：`CCOC(=O)CC(OC(C)=O)c1ccc(C)nc1`
* `ord-2587e99f20af4b9a95cc53879079e3af`
  * 反应物：`CC(=O)O + CC(=O)OCC(=O)Nc1c(C(=O)C(C)(C)O)oc2nc(-c3ccccc3Cl)c(-c3ccc(Cl)cc3)cc12 + CO + O.[Li+].[OH-]`
  * 生成命中：`CC(C)(O)C(=O)c1oc2nc(-c3ccccc3Cl)c(-c3ccc(Cl)cc3)cc2c1NC(=O)CO`
  * 记录产物：`CC(C)(O)C(=O)c1oc2nc(-c3ccccc3Cl)c(-c3ccc(Cl)cc3)cc2c1NC(=O)CO`

### `esterification_intermolecular_001` 酯化(分子间)

* `ord-c6d1437bef5145cca37826ac5ae090f0`
  * 反应物：`CO + Cc1c(C(=O)O)cccc1[N+](=O)[O-] + O=S(Cl)Cl`
  * 生成命中：`COC(=O)c1cccc([N+](=O)[O-])c1C`
  * 记录产物：`COC(=O)c1cccc([N+](=O)[O-])c1C`
* `ord-b36ff282a19946cb9e1721c4f32fd0ac`
  * 反应物：`CCO + O=C(O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2=O)cc1 + O=S(Cl)Cl`
  * 生成命中：`CCOC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2=O)cc1`
  * 记录产物：`CCOC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2=O)cc1`
* `ord-f82b850c17b44c82bd3c88a18c85d0b3`
  * 反应物：`C=Cc1ccccc1CC(C(=O)O)N1C(=O)c2ccccc2C1=O + CCN=C=NCCCN(C)C.Cl + C[Si](C)(C)CCO + c1ccncc1`
  * 生成命中：`C=Cc1ccccc1CC(C(=O)OCC[Si](C)(C)C)N1C(=O)c2ccccc2C1=O`
  * 记录产物：`C=Cc1ccccc1CC(C(=O)OCC[Si](C)(C)C)N1C(=O)c2ccccc2C1=O`

### `condensation_schiff_base_001` 席夫碱生成

* `ord-968da5d345074707bd8ae7f036b4987e`
  * 反应物：`CCN(CC)CC + CCOC(=O)C(N)CC.Cl + O=Cc1ccccc1 + O=S(=O)([O-])[O-].[Mg+2]`
  * 生成命中：`CCOC(=O)C(CC)N=Cc1ccccc1`
  * 记录产物：`CCOC(=O)C(CC)N=Cc1ccccc1`
* `ord-8341607dd237492f8c1a68b89ed51a7c`
  * 反应物：`CC(C)(C)C=O + NC1CCNC1`
  * 生成命中：`CC(C)(C)C=NC1CCNC1`
  * 记录产物：`CC(C)(C)C=NC1CCNC1`
* `ord-7b25920dfe6144a1a723eec9437b7937`
  * 反应物：`CCCCc1ncc(C=O)n1Cc1ccccc1Cl + COC(=O)[C@@H](N)Cc1cccs1 + Cc1ccccc1`
  * 生成命中：`CCCCc1ncc(C=NC(Cc2cccs2)C(=O)OC)n1Cc1ccccc1Cl`
  * 记录产物：`CCCCc1ncc(C=NC(Cc2cccs2)C(=O)OC)n1Cc1ccccc1Cl`

### `amidation_intermolecular_001` 酰胺化(分子间)

* `ord-21393e26ab0b4c64a67d4dbe4b4c6328`
  * 反应物：`C#CCn1c(-c2ccccc2)nc(C(=O)O)c(C)c1=O + C(=NC1CCCCC1)=NC1CCCCC1 + CNC.Cl + c1ccncc1`
  * 生成命中：`C#CCn1c(-c2ccccc2)nc(C(=O)N(C)C)c(C)c1=O`
  * 记录产物：`C#CCn1c(-c2ccccc2)nc(C(=O)N(C)C)c(C)c1=O`
* `ord-21d973d5e9c342b28599ca4532af6af7`
  * 反应物：`C=CCCC(=O)Cl + C=CCCC(=O)O + COC(=O)c1cccc(N)c1 + O=S(Cl)Cl`
  * 生成命中：`C=CCCC(=O)Nc1cccc(C(=O)OC)c1`
  * 记录产物：`C=CCCC(=O)Nc1cccc(C(=O)OC)c1`
* `ord-555bc4c8dfda4c9f9927d3dfcbc0d7ef`
  * 反应物：`Nc1cccc([N+](=O)[O-])c1 + O=C(O)c1ccc([N+](=O)[O-])cc1`
  * 生成命中：`O=C(Nc1cccc([N+](=O)[O-])c1)c1ccc([N+](=O)[O-])cc1`
  * 记录产物：`O=C(Nc1cccc([N+](=O)[O-])c1)c1ccc([N+](=O)[O-])cc1`

### `aminolysis_ester_001` 酯的氨解

* `ord-9db8bda42ddd42569da026335543c4dd`
  * 反应物：`COc1cc(OC)nc(NC(=O)NS(=O)(=O)c2sccc2C(CF)OC(C)=O)n1 + Cl`
  * 生成命中：`COc1cc(OC)nc(NC(=O)NS(=O)(=O)c2sccc2C(O)CF)n1`
  * 记录产物：`COc1cc(OC)nc(NC(=O)NS(=O)(=O)c2sccc2C(O)CF)n1`
* `ord-446b034cd2a240b1811399997a196a51`
  * 反应物：`COC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2)cc1 + COCCN`
  * 生成命中：`COCCNC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2)cc1`
  * 记录产物：`COCCNC(=O)COc1ccc(C(=O)CN2CCN(c3ccncc3)CC2)cc1`
* `ord-cf8e0ae8899349c9bf22fff5e2ff09a3`
  * 反应物：`CC(=O)OC(C)=O + COc1cccc(N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)C(=O)c2ccccc2N)c1`
  * 生成命中：`COc1cccc(N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)C(=O)c2ccccc2NC(C)=O)c1`
  * 记录产物：`COc1cccc(N(CCN2CCC(C(=O)c3ccc(F)cc3)CC2)C(=O)c2ccccc2NC(C)=O)c1`

### `condensation_glycosylation_001` 糖苷化

* `ord-0c6d074bda374bf1ac9566888c34446c`
  * 反应物：`CC(C)(Br)[C@@H]1CC(=O)O[C@H]1O + CC(C)O + Cc1ccc(S(=O)(=O)O)cc1`
  * 生成命中：`CC(C)OC1OC(=O)CC1C(C)(C)Br`
  * 记录产物：`CC(C)OC1OC(=O)CC1C(C)(C)Br`
* `ord-496503ec4aca455e8a4367b940cce6e8`
  * 反应物：`CCOCC.FB(F)F + CO + C[C@H]1[C@@H](O)O[C@@H]2OC3(C)CC[C@H]4[C@H](C)CC[C@@H]1[C@@]24OO3`
  * 生成命中：`COC1OC2OC3(C)CCC4C(C)CCC(C1C)C24OO3`
  * 记录产物：`COC1OC2OC3(C)CCC4C(C)CCC(C1C)C24OO3`
* `ord-fe73c643d9524284b633570bbae68428`
  * 反应物：`CCN(CC)CC + COc1cc(C2CCC(O)O2)cc(OC)c1OC + O=C(OC(=O)C(F)(F)F)C(F)(F)F + O=C1c2ccccc2C(=O)N1CCCO`
  * 生成命中：`COc1cc(C2CCC(OCCCN3C(=O)c4ccccc4C3=O)O2)cc(OC)c1OC`
  * 记录产物：`COc1cc(C2CCC(OCCCN3C(=O)c4ccccc4C3=O)O2)cc(OC)c1OC`

### `addition_michael_thiol_001` Michael加成(硫醇)

* `ord-d9dbb8c843704e72b8d436d338439278`
  * 反应物：`C=CC(=O)NC1C2CC3CC(C2)CC1C3 + CC(C)(C)c1cc(S)cc(C(C)(C)C)c1O + CCN(CC)CC`
  * 生成命中：`CC(C)(C)c1cc(SCCC(=O)NC2C3CC4CC(C3)CC2C4)cc(C(C)(C)C)c1O`
  * 记录产物：`CC(C)(C)c1cc(SCCC(=O)NC2C3CC4CC(C3)CC2C4)cc(C(C)(C)C)c1O`
* `ord-1459bb327c3c4429b7c487d3471ef8df`
  * 反应物：`O=C(O)C=CCC(=O)O + Sc1nc2ccccc2s1`
  * 生成命中：`O=C(O)CC(CC(=O)O)Sc1nc2ccccc2s1`
  * 记录产物：`O=C(O)CC(CC(=O)O)Sc1nc2ccccc2s1`
* `ord-fbab261c40194fdd8da010af0aa35152`
  * 反应物：`C/C=C/C=O + CCCCCCCCCCCCS`
  * 生成命中：`CCCCCCCCCCCCSC(C)CC=O`
  * 记录产物：`CCCCCCCCCCCCSC(C)CC=O`

### `addition_michael_amine_001` Michael加成(胺)

* `ord-41d35a48018a4cf78bfe4a9b41deea1d`
  * 反应物：`C=CC(C)=O + CC(C)(C)C1CCC(c2ccccc2N2CCNCC2)CC1`
  * 生成命中：`CC(=O)CCN1CCN(c2ccccc2C2CCC(C(C)(C)C)CC2)CC1`
  * 记录产物：`CC(=O)CCN1CCN(c2ccccc2C2CCC(C(C)(C)C)CC2)CC1`
* `ord-2597eddf038c410aaf1b84788b5a9f90`
  * 反应物：`CC(=O)C=C=O + Nc1ccc(NCCCC2CCCO2)c(F)c1`
  * 生成命中：`CC(=O)CC(=O)Nc1ccc(NCCCC2CCCO2)c(F)c1`
  * 记录产物：`CC(=O)CC(=O)Nc1ccc(NCCCC2CCCO2)c(F)c1`
* `ord-8882f056f76f4dc1830b0d8993567b22`
  * 反应物：`CC(=O)C=C=O + Nc1ccc(N2CCOCC2)c(C(F)(F)F)c1`
  * 生成命中：`CC(=O)CC(=O)Nc1ccc(N2CCOCC2)c(C(F)(F)F)c1`
  * 记录产物：`CC(=O)CC(=O)Nc1ccc(N2CCOCC2)c(C(F)(F)F)c1`

### `condensation_aldol_001` 醇醛缩合(分子间)

* `ord-eb2ffed42db34070991af4f46a60fd88`
  * 反应物：`CCC(=O)CC + O=Cc1ccccc1`
  * 生成命中：`CCC(=O)C(C)C(O)c1ccccc1`
  * 记录产物：`CCC(=O)C(C)C(O)c1ccccc1`
* `ord-8a968362f88c480f9b0ae8acc65393b9`
  * 反应物：`C(C[*:2])[*:1] + CCOC(C)=O + COc1cccc(C(=O)c2cccc(OC)c2)c1 + N`
  * 生成命中：`CCOC(=O)CC(O)(c1cccc(OC)c1)c1cccc(OC)c1`
  * 记录产物：`CCOC(=O)CC(O)(c1cccc(OC)c1)c1cccc(OC)c1`
* `ord-a8c8653a3de045df8c791130b1c0216b`
  * 反应物：`CCOC(=O)CN=[N+]=[N-] + CC[O-].[Na+] + O=Cc1cccnc1Cl`
  * 生成命中：`CCOC(=O)C(N=[N+]=[N-])C(O)c1cccnc1Cl`
  * 记录产物：`CCOC(=O)C(N=[N+]=[N-])C(O)c1cccnc1Cl`

### `elimination_amide_to_nitrile_001` 酰胺脱水成腈

* `ord-4de2e5c5af6b486c8884eeb767fb4238`
  * 反应物：`CC(=O)OO + NC(=O)c1cc(Cl)ccn1 + O=C(OC(=O)C(F)(F)F)C(F)(F)F + O=C([O-])[O-].[K+].[K+]`
  * 生成命中：`N#Cc1cc(Cl)ccn1`
  * 记录产物：`N#Cc1cc(Cl)ccn1`
* `ord-0decf2fbbf764e13806159996ca3156c`
  * 反应物：`CC(Nc1cncc(-n2cnc3ccc(C(N)=O)cc32)n1)c1cccc(F)c1 + O=P(Cl)(Cl)Cl`
  * 生成命中：`CC(Nc1cncc(-n2cnc3ccc(C#N)cc32)n1)c1cccc(F)c1`
  * 记录产物：`CC(Nc1cncc(-n2cnc3ccc(C#N)cc32)n1)c1cccc(F)c1`
* `ord-9c9dcda28fe244a7982077b1f6608d72`
  * 反应物：`COc1cccc(CC(N)=O)c1 + O=S(Cl)Cl`
  * 生成命中：`COc1cccc(CC#N)c1`
  * 记录产物：`COc1cccc(CC#N)c1`

### `oxidation_sulfoxide_to_sulfone_001` 亚砜氧化成砜

* `ord-7cbd6652612f4c55b07a8147385f28b2`
  * 反应物：`Cc1onc(-c2ccccc2)c1-c1cc(F)c(S(C)=O)c(F)c1 + O.O.O.O.O.O.O=C([O-])c1ccccc1C(=O)O[O-].[Mg+2] + O=S(=O)([O-])O[O-].[K+].[K+]`
  * 生成命中：`Cc1onc(-c2ccccc2)c1-c1cc(F)c(S(C)(=O)=O)c(F)c1`
  * 记录产物：`Cc1onc(-c2ccccc2)c1-c1cc(F)c(S(C)(=O)=O)c(F)c1`
* `ord-b03d103511ba46508cce9d5472c584ca`
  * 反应物：`CS(=O)C[C@H](NC(=O)OCc1ccccc1)C(=O)N[C@@H](Cc1ccccc1)[C@H](O)C[C@@]1(C(=O)[NH2+][O-])CCCN1C(C)(C)C.N#N + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC(C)(C)N1CCCC1(CC(O)C(Cc1ccccc1)NC(=O)C(CS(C)(=O)=O)NC(=O)OCc1ccccc1)C(=O)[NH2+][O-]`
  * 记录产物：`CC(C)(C)N1CCCC1(CC(O)C(Cc1ccccc1)NC(=O)C(CS(C)(=O)=O)NC(=O)OCc1ccccc1)C(=O)[NH2+][O-] ; CC(C)(C)N1CCCC1(CC(O)C(Cc1ccccc1)NC(=O)C(CS(C)(=O)=O)NC(=O)OCc1ccccc1)C(=O)[NH2+][O-].N#N.O ; N#N ; O`
* `ord-452a3c48ba9c42cea004229928dd9ac8`
  * 反应物：`CC1=C(CC(=O)O)c2cc(F)c(F)cc2C1=Cc1ccc(S(C)=O)cc1 + O=C(OO)c1cccc(Cl)c1`
  * 生成命中：`CC1=C(CC(=O)O)c2cc(F)c(F)cc2C1=Cc1ccc(S(C)(=O)=O)cc1`
  * 记录产物：`CC1=C(CC(=O)O)c2cc(F)c(F)cc2C1=Cc1ccc(S(C)(=O)=O)cc1`

### `reduction_sulfoxide_001` 亚砜还原成硫醚

* `ord-9bd323dfdfc3445abcf8bcd679f410ce`
  * 反应物：`CO + COc1cc(OCCS(C)(=O)=O)ccc1NC(=O)[C@@H]1N[C@@H](CC(C)(C)C)[C@@]2(C(=O)Nc3cc(Cl)ccc32)[C@H]1c1cccc(Cl)c1F`
  * 生成命中：`COc1cc(OCCS(C)=O)ccc1NC(=O)C1NC(CC(C)(C)C)C2(C(=O)Nc3cc(Cl)ccc32)C1c1cccc(Cl)c1F`
  * 记录产物：`COc1cc(OCCS(C)=O)ccc1NC(=O)C1NC(CC(C)(C)C)C2(C(=O)Nc3cc(Cl)ccc32)C1c1cccc(Cl)c1F`
* `ord-3caaed4844244114b6f8629face0a542`
  * 反应物：`CC(C)=O + CON=C(C(=O)NC1C(=O)N2C(C(=O)OC(c3ccccc3)c3ccccc3)=C(COC(=O)N3CCN(C)CC3)CS(=O)[C@H]12)c1nsc(N)n1 + O=C(OC(=O)C(F)(F)F)C(F)(F)F + [I-].[Na+]`
  * 生成命中：`CON=C(C(=O)NC1C(=O)N2C(C(=O)OC(c3ccccc3)c3ccccc3)=C(COC(=O)N3CCN(C)CC3)CSC12)c1nsc(N)n1`
  * 记录产物：`CON=C(C(=O)NC1C(=O)N2C(C(=O)OC(c3ccccc3)c3ccccc3)=C(COC(=O)N3CCN(C)CC3)CSC12)c1nsc(N)n1`
* `ord-b7aa1f4da056454fbd5c81aea55bbaa3`
  * 反应物：`Cc1ccc([S@](=O)C[C@](O)(CC(C)(C)c2cc(Br)cc3c2OCC3)C(F)(F)F)cc1 + O=C(OC(=O)C(F)(F)F)C(F)(F)F + [I-].[Na+]`
  * 生成命中：`Cc1ccc(SCC(O)(CC(C)(C)c2cc(Br)cc3c2OCC3)C(F)(F)F)cc1`
  * 记录产物：`Cc1ccc(SCC(O)(CC(C)(C)c2cc(Br)cc3c2OCC3)C(F)(F)F)cc1`

### `oxidation_diphenol_para_001` 对二酚氧化成醌

* `ord-5e6a35ae7d31484597e3dd3d9eaeb9f3`
  * 反应物：`Cc1cc(O)ccc1O + O=O + O=S(=O)(O)O`
  * 生成命中：`CC1=CC(=O)C=CC1=O`
  * 记录产物：`CC1=CC(=O)C=CC1=O`
* `ord-de8eeb5a0f4e441ca9929962dbdd5c1a`
  * 反应物：`O=S(=O)(c1ccccc1)c1cc(O)c2ccccc2c1O`
  * 生成命中：`O=C1C=C(S(=O)(=O)c2ccccc2)C(=O)c2ccccc21`
  * 记录产物：`O=C1C=C(S(=O)(=O)c2ccccc2)C(=O)c2ccccc21`
* `ord-ae9f081be80842a1940c73492fb84164`
  * 反应物：`COc1ccc([Te](=O)c2ccc(OC)cc2)cc1 + Oc1ccc(O)c2ccccc12`
  * 生成命中：`O=C1C=CC(=O)c2ccccc21`
  * 记录产物：`COc1ccc([Te]c2ccc(OC)cc2)cc1 ; O=C1C=CC(=O)c2ccccc21`

### `reduction_quinone_para_001` 对醌还原成二酚

* `ord-d264a4b8ce364c998253ee55ac74f6a8`
  * 反应物：`CCN(C(C)C)C(C)C + COC1=CC(=O)C=C(OC)C1=O + O + O=C(O)CCS`
  * 生成命中：`COc1cc(O)cc(OC)c1O`
  * 记录产物：`COc1cc(O)cc(OC)c1O ; COc1cc(O)cc(OC)c1O.O=C(O)CCS ; O=C(O)CCS`
* `ord-0fa0833f8c414229aadad5df5cceafad`
  * 反应物：`CO + O=C1C=C(Cl)C(=O)C2C1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
  * 生成命中：`Oc1cc(Cl)c(O)c2c1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
  * 记录产物：`Oc1cc(Cl)c(O)c2c1C1(Cl)C(Cl)=C(Cl)C2(Cl)C1(Cl)Cl`
* `ord-882cd14c17ef48f1a4869be62db102ee`
  * 反应物：`C + CC1=C(C)C(=O)C(CC[C@](C)(O)CO)=C(C)C1=O + [H][H]`
  * 生成命中：`Cc1c(C)c(O)c(CCC(C)(O)CO)c(C)c1O`
  * 记录产物：`Cc1c(C)c(O)c(CCC(C)(O)CO)c(C)c1O`

### `cyclization_macro_lactam_001` 大环内酰胺化（同一分子内羧酸 + 铵盐）

* `ord-c763472b558f4bf19c166b3b739155cb`
  * 反应物：`CCN(C(C)C)C(C)C + COc1ccc([C@@H](C)[NH3+])nc1.[Cl-] + C[C@H](C(=O)O)c1ccc(-c2ccccc2)c(F)c1 + ClCCCl`
  * 生成命中：`COc1ccc(C(C)NC(=O)C(C)c2ccc(-c3ccccc3)c(F)c2)nc1`
  * 记录产物：`COc1ccc(C(C)NC(=O)C(C)c2ccc(-c3ccccc3)c(F)c2)nc1`
* `ord-5ad34635f4874236982f9ead8b5b9a65`
  * 反应物：`CCN(C(C)C)C(C)C + COC(=O)c1cccc(C[NH3+])c1.[Cl-] + COc1ccc(C(=O)O)cc1OC + ClCCCl`
  * 生成命中：`COC(=O)c1cccc(CNC(=O)c2ccc(OC)c(OC)c2)c1`
  * 记录产物：`COC(=O)c1cccc(CNC(=O)c2ccc(OC)c(OC)c2)c1`
* `ord-7a28c3a922934445a708448c217e5192`
  * 反应物：`Cc1cc(N2CCN(CCOc3ccccc3)C2=O)sc1C(=O)O + Cc1cc(N2CCN(Cc3ccc(F)cc3)C2=O)sc1C(=O)O + [Cl-].[NH3+]Cc1cnc2ccccc2c1`
  * 生成命中：`Cc1cc(N2CCN(Cc3ccc(F)cc3)C2=O)sc1C(=O)NCc1cnc2ccccc2c1`
  * 记录产物：`Cc1cc(N2CCN(Cc3ccc(F)cc3)C2=O)sc1C(=O)NCc1cnc2ccccc2c1`

### `addition_isocyanate_amine_urea_001` 异氰酸酯 + 胺 -> 脲

* `ord-c855ba8a68d94a90a16f7359111ea10d`
  * 反应物：`CC(Cl)Cl + CN + CN1C(=O)CN=C(c2ccccc2F)c2c1ccc(N)c2Cl + CN1C(=O)CN=C(c2ccccc2F)c2c1ccc(N=C=O)c2Cl`
  * 生成命中：`CNC(=O)Nc1ccc2c(c1Cl)C(c1ccccc1F)=NCC(=O)N2C`
  * 记录产物：`CNC(=O)Nc1ccc2c(c1Cl)C(c1ccccc1F)=NCC(=O)N2C`

### `coupling_suzuki_biaryl_001` Suzuki 偶联（芳基溴 + 芳基硼酸 -> 联苯）

* `ord-19b3524e42254cd798a618b4d5e376b5`
  * 反应物：`CCN(CC)CC + CCc1cc(OCc2ccc(B(O)O)cc2)c2ccccc2n1.Cl + N#Cc1ccccc1Br`
  * 生成命中：`CCc1cc(OCc2ccc(-c3ccccc3C#N)cc2)c2ccccc2n1`
  * 记录产物：`CCc1cc(OCc2ccc(-c3ccccc3C#N)cc2)c2ccccc2n1`
* `ord-2e87ef03d13944988967e1bb4dcac910`
  * 反应物：`OB(O)c1ccc(Cl)cc1 + Oc1ccc2nc(-c3ccc(O)c(F)c3)cc(Br)c2c1`
  * 生成命中：`Oc1ccc2nc(-c3ccc(O)c(F)c3)cc(-c3ccc(Cl)cc3)c2c1`
  * 记录产物：`Oc1ccc2nc(-c3ccc(O)c(F)c3)cc(-c3ccc(Cl)cc3)c2c1`
* `ord-505d378986564b289b6586ca9291e8b6`
  * 反应物：`Brc1ccc2c(c1)C1(CCCCC1)C(=NOCc1ccccc1)N2 + CCCCCC + COc1cccc(B(O)O)c1`
  * 生成命中：`COc1cccc(-c2ccc3c(c2)C2(CCCCC2)C(=NOCc2ccccc2)N3)c1`
  * 记录产物：`COc1cccc(-c2ccc3c(c2)C2(CCCCC2)C(=NOCc2ccccc2)N3)c1`

### `coupling_sonogashira_aryl_alkyne_001` Sonogashira 偶联（芳基溴 + 端炔 -> 芳基炔）

* `ord-0dbb83c791174a899436c4d40bf3aa58`
  * 反应物：`C#Cc1ccccc1 + Nc1ncc(C(F)(F)F)cc1Br + O`
  * 生成命中：`Nc1ncc(C(F)(F)F)cc1C#Cc1ccccc1`
  * 记录产物：`Nc1ncc(C(F)(F)F)cc1C#Cc1ccccc1`
* `ord-bd280274d3164bc1abeaa913cf194cbf`
  * 反应物：`C#C[Si](C)(C)C + CCN(CC)CC + N#Cc1cc(F)cc(Br)c1`
  * 生成命中：`C[Si](C)(C)C#Cc1cc(F)cc(C#N)c1`
  * 记录产物：`C[Si](C)(C)C#Cc1cc(F)cc(C#N)c1`
* `ord-ac88b083643c4694ae3373a4a8eb478e`
  * 反应物：`Brc1ccc(C2(NCc3ccccc3)CC2)cc1 + C#C[Si](C)(C)C`
  * 生成命中：`C[Si](C)(C)C#Cc1ccc(C2(NCc3ccccc3)CC2)cc1`
  * 记录产物：`C[Si](C)(C)C#Cc1ccc(C2(NCc3ccccc3)CC2)cc1`

### `coupling_n_arylation_amine_001` Buchwald–Hartwig 型 N-芳基化（芳基溴 + 胺）

* `ord-e666274769674ed785f5d9ad4ef36895`
  * 反应物：`C1COCCO1 + CSc1cc(-c2cnn(C)c2N)ncn1 + Cc1ccc(NC(=O)c2cccc(C(F)(F)F)c2)cc1Br + O=C([O-])[O-].[Cs+].[Cs+]`
  * 生成命中：`CSc1cc(-c2cnn(C)c2Nc2cc(NC(=O)c3cccc(C(F)(F)F)c3)ccc2C)ncn1`
  * 记录产物：`CSc1cc(-c2cnn(C)c2Nc2cc(NC(=O)c3cccc(C(F)(F)F)c3)ccc2C)ncn1`
* `ord-26a7fcbaf54e431ca865fbca56d6db18`
  * 反应物：`CC1(C)c2cccc(P(c3ccccc3)c3ccccc3)c2Oc2c(P(c3ccccc3)c3ccccc3)cccc21 + CN1CCN(C(=O)c2ccc(Br)cc2)CC1 + COc1ccc(Cl)c(-c2cc(C)c3nc(N)nnc3c2)c1 + O=C([O-])[O-].[Cs+].[Cs+]`
  * 生成命中：`COc1ccc(Cl)c(-c2cc(C)c3nc(Nc4ccc(C(=O)N5CCN(C)CC5)cc4)nnc3c2)c1`
  * 记录产物：`COc1ccc(Cl)c(-c2cc(C)c3nc(Nc4ccc(C(=O)N5CCN(C)CC5)cc4)nnc3c2)c1`
* `ord-e604cb0789b14f32a33b0a9fab1c99d1`
  * 反应物：`Brc1ccc(SCCN2CCCC2)cc1 + CC1(C)c2cccc(P(c3ccccc3)c3ccccc3)c2Oc2c(P(c3ccccc3)c3ccccc3)cccc21 + COc1ccc(Cl)c(-c2cc(C)c3nc(N)nnc3c2)c1 + O=C([O-])[O-].[Cs+].[Cs+]`
  * 生成命中：`COc1ccc(Cl)c(-c2cc(C)c3nc(Nc4ccc(SCCN5CCCC5)cc4)nnc3c2)c1`
  * 记录产物：`COc1ccc(Cl)c(-c2cc(C)c3nc(Nc4ccc(SCCN5CCCC5)cc4)nnc3c2)c1`

### `acylation_alcohol_anhydride_001` 醇的 O-酰化（酸酐 + 醇 -> 酯）

* `ord-00533d2621284180b8d6e372c9496cb7`
  * 反应物：`CC(=O)OC(C)=O + CCOC(C)=O + CN(C)c1ccccn1 + O[C@@H]1C=C[C@H](OC2CCCCO2)C1`
  * 生成命中：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
  * 记录产物：`CC(=O)OC1C=CC(OC2CCCCO2)C1`
* `ord-51ef9f6ae2d14a58b7d97c8023ad50fd`
  * 反应物：`CC(=O)OC(C)=O + CCOC(=O)CC(O)c1ccc(C)nc1 + [Na+].[OH-] + c1ccncc1`
  * 生成命中：`CCOC(=O)CC(OC(C)=O)c1ccc(C)nc1`
  * 记录产物：`CCOC(=O)CC(OC(C)=O)c1ccc(C)nc1`
* `ord-c66ac16f92a140a99bf16ac4d992dd53`
  * 反应物：`CC(=O)OC(C)=O + COc1ccc(C2CCC(O)CC2NC(=O)c2ccc(OCC3CC3)c(OCC3CC3)c2)cc1OC`
  * 生成命中：`COc1ccc(C2CCC(OC(C)=O)CC2NC(=O)c2ccc(OCC3CC3)c(OCC3CC3)c2)cc1OC`
  * 记录产物：`COc1ccc(C2CCC(OC(C)=O)CC2NC(=O)c2ccc(OCC3CC3)c(OCC3CC3)c2)cc1OC`

### `substitution_alcohol_thionyl_001` 醇的氯代（醇 + 亚硫酰氯 -> 氯代烷）

* `ord-c9fda451c4c64a4baef159b8914061f8`
  * 反应物：`CCO + O=C(O)[C@H]1C[C@@H](O)CN1 + O=S(Cl)Cl`
  * 生成命中：`Cl`
  * 记录产物：`CCOC(=O)C1CC(O)CN1 ; CCOC(=O)C1CC(O)CN1.Cl ; Cl`
* `ord-ab828ab4f8de435cbeaf92e3a367de83`
  * 反应物：`CC1CNCCC1C(=O)O.Cl + CCO + O=S(Cl)Cl`
  * 生成命中：`Cl`
  * 记录产物：`CCOC(=O)C1CCNCC1C ; CCOC(=O)C1CCNCC1C.Cl ; Cl`
* `ord-31132c42a0fd482cafc5a6621aa9e049`
  * 反应物：`CCCCN(CC(=O)O)C(=O)[C@H](CCCNC(=N)N)NS(=O)(=O)c1ccc2ccccc2c1.N#N + CCO + O=S(Cl)Cl`
  * 生成命中：`Cl`
  * 记录产物：`CCCCN(CC(=O)OCC)C(=O)C(CCCNC(=N)N)NS(=O)(=O)c1ccc2ccccc2c1 ; CCCCN(CC(=O)OCC)C(=O)C(CCCNC(=N)N)NS(=O)(=O)c1ccc2ccccc2c1.Cl.N#N ; Cl ; N#N`

### `substitution_alcohol_thionyl_family_001` 醇的氯代（伯/仲/苄醇族 + 亚硫酰氯）

* `ord-b1be6064558b4bf8b5568e3fb5a9afe1`
  * 反应物：`CN(C)C=O + O=S(Cl)Cl + OCCCOCCc1cccc2sccc12`
  * 生成命中：`ClCCCOCCc1cccc2sccc12`
  * 记录产物：`ClCCCOCCc1cccc2sccc12`
* `ord-dee3bbe8fbf245858780f3dd89a7ddd2`
  * 反应物：`O=S(Cl)Cl + OCc1ccncc1`
  * 生成命中：`ClCc1ccncc1`
  * 记录产物：`Cl ; Cl.ClCc1ccncc1 ; ClCc1ccncc1`
* `ord-dee3bbe8fbf245858780f3dd89a7ddd2`
  * 反应物：`O=S(Cl)Cl + OCc1ccncc1`
  * 生成命中：`Cl`
  * 记录产物：`Cl ; Cl.ClCc1ccncc1 ; ClCc1ccncc1`

### `coupling_n_alkylation_benzyl_001` 苄基/杂芳甲基氯的 N-烷基化

* `ord-5552549c3a7244c2a7f25a78047820a8`
  * 反应物：`CC(C)(C)c1cn(Cc2ccccc2)c([C@H](N)Cc2c[nH]c3ccccc23)n1 + CCN(CC)CC + ClCc1ccccc1`
  * 生成命中：`CC(C)(C)c1cn(Cc2ccccc2)c(C(Cc2c[nH]c3ccccc23)NCc2ccccc2)n1`
  * 记录产物：`CC(C)(C)c1cn(Cc2ccccc2)c(C(Cc2c[nH]c3ccccc23)NCc2ccccc2)n1`
* `ord-7fa9a543ff6a42ba8c85a7a23afb39d9`
  * 反应物：`CC(C)c1nc(CCl)co1 + CN`
  * 生成命中：`CNCc1coc(C(C)C)n1`
  * 记录产物：`CNCc1coc(C(C)C)n1`
* `ord-14ad940e92ac4243ac1b9cc8a245e186`
  * 反应物：`CCN(CC)CC + CCOC(=O)CN.Cl + O=[N+]([O-])c1ccc(Cl)cc1CCl`
  * 生成命中：`CCOC(=O)CNCc1cc(Cl)ccc1[N+](=O)[O-]`
  * 记录产物：`CCOC(=O)CNCc1cc(Cl)ccc1[N+](=O)[O-]`

### `acylation_alcohol_cyclic_succinic_001` 醇的 O-酰化（丁二酸酐开环 -> 单酯）

* `ord-d8d5f6909a9d42dca945fc4afe484978`
  * 反应物：`CN(C)C=O + O=C1CCC(=O)O1 + O=C1O[C@@H](Cn2ccnn2)CN1c1ccc(-c2ccc(C3=NO[C@H](CO)C3)nc2)c(F)c1 + c1ccncc1`
  * 生成命中：`O=C(O)CCC(=O)OCC1CC(c2ccc(-c3ccc(N4CC(Cn5ccnn5)OC4=O)cc3F)cn2)=NO1`
  * 记录产物：`O=C(O)CCC(=O)OCC1CC(c2ccc(-c3ccc(N4CC(Cn5ccnn5)OC4=O)cc3F)cn2)=NO1`
* `ord-6294c2bf7f454cdbad3246340af72d9c`
  * 反应物：`O=C(O)CC(O)(CC(=O)O)C(=O)O + O=C1CCC(=O)O1 + OCc1ccccc1 + c1ccncc1`
  * 生成命中：`O=C(O)CCC(=O)OCc1ccccc1`
  * 记录产物：`O=C(O)CCC(=O)OCc1ccccc1`
* `ord-3c50555f4f484c72bdffa807ed8b8b0f`
  * 反应物：`C=C[C@H]1CN2CCC1C[C@@H]2[C@@H](O)c1ccnc2ccc(OC)cc12 + CO + Cc1ccccc1 + O=C1OC(=O)[C@H]2[C@@H]1[C@@H]1C=C[C@H]2C1`
  * 生成命中：`COC(=O)C1C2C=CC(C2)C1C(=O)O`
  * 记录产物：`COC(=O)C1C2C=CC(C2)C1C(=O)O`

### `acylation_alcohol_cyclic_phthalic_001` 醇的 O-酰化（邻苯二甲酸酐开环 -> 单酯）

* `ord-3dbead96b25644bab899c35c4bc7ec16`
  * 反应物：`CNC(=O)c1c2cc(C3CC3)c(N(CCO)S(C)(=O)=O)cc2nn1-c1ccc(F)cc1 + O=C1OC(=O)c2ccccc21`
  * 生成命中：`CNC(=O)c1c2cc(C3CC3)c(N(CCOC(=O)c3ccccc3C(=O)O)S(C)(=O)=O)cc2nn1-c1ccc(F)cc1`
  * 记录产物：`CNC(=O)c1c2cc(C3CC3)c(N(CCOC(=O)c3ccccc3C(=O)O)S(C)(=O)=O)cc2nn1-c1ccc(F)cc1`
* `ord-962249844c1c4960ba42236fd6ee7f5e`
  * 反应物：`C#CC(C)(O)CCc1c(C)c(OC(C)=O)c(C)c(C)c1OC(C)=O + CCN(CC)CC + O=C1OC(=O)c2ccccc21`
  * 生成命中：`C#CC(C)(CCc1c(C)c(OC(C)=O)c(C)c(C)c1OC(C)=O)OC(=O)c1ccccc1C(=O)O`
  * 记录产物：`C#CC(C)(CCc1c(C)c(OC(C)=O)c(C)c(C)c1OC(C)=O)OC(=O)c1ccccc1C(=O)O`
* `ord-1cc4507b4a854a03a6da1001749d07ed`
  * 反应物：`CO + O=C1OC(=O)c2ccccc21`
  * 生成命中：`COC(=O)c1ccccc1C(=O)O`
  * 记录产物：`COC(=O)c1ccccc1C(=O)O`

## 失败/无命中说明

* 没有 `product_match` 的规则不等于“规则错”：可能是 ORD 抽样里没有该反应类型、底物取代基不匹配、规则要求多步/共试剂，或记录方向相反。
* `run_errors` 是 RDKit 在具体底物上抛错的次数，已逐条累计；`invalid_products` 是生成物无法规范化的次数。
* 需要外部权威规则来源时，下一步应查论文/数据集原文；本报告只回答“有没有在 ORD 真实记录里跑出相同产物”。
