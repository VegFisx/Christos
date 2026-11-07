# 文献一致性验证结果

生成时间：2026-10-31 00:39:09

验证类型：计算实验（回溯性文献一致性检查），不是湿实验。

汇总：5/5 产物连接层命中；5/5 使用预期反应族；3/5 在 PubChem 立体结构重跑中得到完整立体结构命中；5/5 至少得到连接层命中。

本地二维运行：5/5 连接层命中（结构与文献产物一致）。
PubChem 立体重跑：3/5 完整立体命中；5/5 连接层命中。

统一运行条件：煎煮，100°C，60 分钟，pH 6.5，空气，一轮，每个底物对最多 64 个产物。

| 案例 | 本地拓扑命中 | 规则族一致 | PubChem 立体结构重跑 | 连通层一致 | 规则 | 分子式差（产物-底物） | 文献中间体 | 本地立体状态 |
|---|---|---|---|---|---|---|---|---|
| 甘草酸 → 甘草次酸 | hit | 是 | exact_stereo_hit | 是 | hydrolysis_glycoside_001 | C-12 H-16 O-12 | glycyrrhetinic acid 3-O-mono-beta-D-glucuronide：not_in_local_db | unspecified |
| 人参皂苷 Rb1 → Rg3 | hit | 是 | exact_stereo_hit | 是 | hydrolysis_glycoside_001 | C-12 H-20 O-10 | Ginsenoside rd：observed，续到目标=True | unspecified |
| 乌头碱 → 苯甲酰乌头原碱 | hit | 是 | connectivity_only | 是 | hydrolysis_ester_001 | C-2 H-2 O-1 | 未定义 | unspecified |
| 苯甲酰乌头原碱 → 乌头原碱 | hit | 是 | connectivity_only | 是 | hydrolysis_ester_001 | C-7 H-4 O-1 | 未定义 | unspecified |
| 芦丁 → 槲皮素 | hit | 是 | exact_stereo_hit | 是 | hydrolysis_glycoside_001 | C-12 H-20 O-9 | Isoquercitrin：observed，续到目标=True；Isoquercitin：observed；Isoquercetrin：not_observed | none |

## 路径对照（引擎 vs 文献）

| 案例 | 引擎路径（二维运行） | 立体重跑 | 文献路径 | 中间体 | 判定 |
|---|---|---|---|---|---|
| 甘草酸 → 甘草次酸 | hydrolysis_glycoside_001，断键 C–O，第 1 轮，分子式差 C-12 H-16 O-12 | exact_stereo_hit（hydrolysis_glycoside_001，断键 C–O） | Hydrothermal hydrolysis produces glycyrrhetinic acid and glycyrrhetinic acid 3-O-mono-beta-D-glucuronide through consecutive and parallel reactions. | glycyrrhetinic acid 3-O-mono-beta-D-glucuronide（not_in_local_db） | 反应族一致。文献同时报告单葡萄糖醛酸中间体和连续/并行水解；该中间体不在本地成分表中，因此本轮无法确认具体先后顺序。 |
| 人参皂苷 Rb1 → Rg3 | hydrolysis_glycoside_001，断键 C–O，第 1 轮，分子式差 C-12 H-20 O-10 | exact_stereo_hit（hydrolysis_glycoside_001，断键 C–O） | Enzymatic conversion proceeds from Rb1 through ginsenoside Rd to Rg3; thermal processing also forms Rg3 through glycoside hydrolysis and elimination. | Ginsenoside rd（observed，续到目标） | 文献的 Rb1 → Rd → Rg3 序列可通过两次单轮运行复现。另一轮运行中，引擎也能从 Rb1 直接得到 Rg3，因此允许一条文献发酵实验未描述的捷径。本地结构缺少立体化学信息。 |
| 乌头碱 → 苯甲酰乌头原碱 | hydrolysis_ester_001，断键 O–C，第 1 轮，分子式差 C-2 H-2 O-1 | connectivity_only（hydrolysis_ester_001，断键 O–C） | Hydrolysis removes the C8 acetylester from the diester C19-diterpenoid skeleton. | 未定义 | 规则族和脱去片段 C2H2O（对应乙酰基）均符合 C8 乙酸酯水解。本地二维结构无法提供原子映射级的 C8 位点确认。 |
| 苯甲酰乌头原碱 → 乌头原碱 | hydrolysis_ester_001，断键 O–C，第 1 轮，分子式差 C-7 H-4 O-1 | connectivity_only（hydrolysis_ester_001，断键 O–C） | Further hydrolysis removes the C14 benzoylester and gives aconine. | 未定义 | 规则族和脱去片段 C7H4O（对应苯甲酰基）均符合 C14 苯甲酸酯水解。两步乌头碱水解也可分别跑通。本地二维结构无法提供原子映射级的 C14 位点确认。 |
| 芦丁 → 槲皮素 | hydrolysis_glycoside_001，断键 C–O，第 1 轮，分子式差 C-12 H-20 O-9 | exact_stereo_hit（hydrolysis_glycoside_001，断键 C–O） | Acid or subcritical-water treatment cleaves the rutinoside glycosidic bond; isoquercetin is also observed as a product. | Isoquercitrin（observed，续到目标）；Isoquercitin（observed）；Isoquercetrin（not_observed） | 文献中间体异槲皮素出现在同一轮候选中，并从它单独起跑可生成槲皮素。目标产物也在糖苷键水解层面与文献路径一致。 |

## 逐案判定

- **甘草酸 → 甘草次酸**：反应族一致。文献同时报告单葡萄糖醛酸中间体和连续/并行水解；该中间体不在本地成分表中，因此本轮无法确认具体先后顺序。
- **人参皂苷 Rb1 → Rg3**：文献的 Rb1 → Rd → Rg3 序列可通过两次单轮运行复现。另一轮运行中，引擎也能从 Rb1 直接得到 Rg3，因此允许一条文献发酵实验未描述的捷径。本地结构缺少立体化学信息。
- **乌头碱 → 苯甲酰乌头原碱**：规则族和脱去片段 C2H2O（对应乙酰基）均符合 C8 乙酸酯水解。本地二维结构无法提供原子映射级的 C8 位点确认。
- **苯甲酰乌头原碱 → 乌头原碱**：规则族和脱去片段 C7H4O（对应苯甲酰基）均符合 C14 苯甲酸酯水解。两步乌头碱水解也可分别跑通。本地二维结构无法提供原子映射级的 C14 位点确认。
- **芦丁 → 槲皮素**：文献中间体异槲皮素出现在同一轮候选中，并从它单独起跑可生成槲皮素。目标产物也在糖苷键水解层面与文献路径一致。

判定口径：

- “产物命中”要求目标分子按本地库中的非映射 SMILES 规范化后完全一致。
- “规则族一致”要求产物命中路径使用该文献所述的水解规则。
- “分子式差”用于标示模型实际脱去的基团；它不替代原子映射级的机理证明。
- 本地结构若缺少立体化学，记录为 `unspecified`，不能宣称验证了文献中的特定立体异构体。
- PubChem 检查使用带立体化学的参考结构重新运行；该结果与本地库结果分开报告。
- 文献中间体只有在本地库中存在时才做观察记录；缺失时写 `not_in_local_db`。
- 对观察到的中间体再独立运行一轮；`intermediate_to_target=true` 表示该中间体可继续生成目标。

逐案例文献和路径细节见同目录 JSON。
