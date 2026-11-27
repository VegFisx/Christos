# 炮制留出集：规则族状态与剩余问题（2026-11-27）

结论先写：**之前列的五个“缺失规则族”已经全部补上、激活、带文献出处，并且在 1 轮里就能命中对应案例。**
现在没有彻底解决的，不是规则族，而是**选择性/可行性**：多跑几轮能把 21 条文献产物全部找出来，也会让 10 条“预期不产生”的负对照里的 9 条冒出产物。这是 `AGENTS.md` §11.8 记录的已知缺陷，不是再补几条规则能解决的。

## 一、五个规则族：已实现，r1 命中

| 规则族 | 规则 ID | 状态 | 文献出处（notes 内） | r1 留出集案例 |
|---|---|---|---|---|
| 13,28-环氧醚开环/异构化 | `isomerization_cyclic_ether_saponin_001` | active / cited | 10.7501/j.issn.0253-2670.2017.02.019；中国药科大学学报 2012,43(4):334-342 | 柴胡皂苷 A→b1：consistent |
| 芳香甲氧基 O-去甲基 | `demethylation_aromatic_o_001` | active / cited | 10.3969/j.issn.1001-1528.2010.03.028；中成药 2021,43(11):3082-3088；现代药物与临床 2015,30(1):18-23 | 巴马汀→巴马红汀：consistent |
| HMF 连续脱水/环化 | `dehydration_cyclization_hmf_fructose_001` | active / cited | 10.1155/2022/3382333；中草药 2026,14；专利 CN114858934B | 果糖→5-HMF：consistent |
| N-去甲基 + 氧化/芳构化 | `oxidation_n_demethylation_aromatization_001` | active / cited | S1876081308600433；中国实验方剂学杂志 2011,17(7) | 吴茱萸碱→吴茱萸次碱：consistent |
| 士的宁/马钱子碱重排 | `rearrangement_strychnos_alkaloid_001` | active / cited | 10.13313/j.issn.1673-4890.20230201001；10.1248/cpb.38.1295 | 士的宁→异士的宁：consistent（负对照） |

这些规则不是手写 SMARTS；notes 记录为文献反应对经 RXNMapper+RDChiral 派生。规则文件按 §0.2 冻结，未按留出集调整。

## 二、“连续水解”不是缺规则，是缺轮数

番泻苷 A（连剥两个葡萄糖）、甘遂二酯（连续两次酯水解）、黄芪乙酰黄芪苷（脱乙酰到黄芪甲苷 IV）、天麻素（水解 + 苄位氧化）在 r1 到不了，但 r3 都能到。它们用的是已有的 `hydrolysis_glycoside_001`、`hydrolysis_ester_001`、`oxidation_benzylic_alcohol_001`，不需要新规则。

## 三、当前两组数字（同一批 31 条冻结案例）

| 配置 | 21 条阳性（文献给出产物） | 10 条负对照（预期不产生） |
|---|---|---|
| r1（默认） | 20/21 骨架级命中（95.2%） | 5/10 也出现产物 |
| r3（开发配置） | **21/21 骨架级命中（100%）** | **9/10 也出现产物** |

- 阳性补充：2 条 formula-only 的参考结构已由 tcm.db 条目确定性推导，结构复核后合并为 20/21；r3 时 21/21。
- 苍术苷那条：骨架一致，全键立体不一致（引擎 `FYQXODZRNSCOTR-UPWBHRCRSA-N` vs 参考 `FYQXODZRNSCOTR-QLKRWLHJSA-N`）；生产模式的立体枚举也没有补出正确立体异构体。这是脱羧规则的立体化学限制，规则冻结，记录为已知限制。
- ligustroside：r3 仍是 miss，但它是负对照；原案例 seed 侧链是 tyrosol，目标是 hydroxytyrosol，属于案例设计问题，不是阳性漏检。

## 四、处理决定

1. **论文主分数用 r1（20/21）**：这是默认配置，且与冻结预期、可复现命令一致。
2. **r3 只作为开发配置报告**：它给出召回上限 21/21，同时把负对照命中从 5/10 推到 9/10；不宣称它更好。
3. **不再补规则、不加基于案例的选择性启发式**：选择性是已知缺陷（§11.8），没有文献标定的可行性判据前，补规则只会同时抬高召回和假阳性。用户 2026-11-27 明确：**当前阶段不要求“别乱出产物”**，验收口径仍是文献标出的产物必须出现；负对照命中只作选择性诊断，不作拦截条件。
4. **要真正解决选择性，需要新的数据/模型**（同一底物的时间序列、竞争反应、实验产率），不是当前框架层能补的。等有这类数据再做。

## 五、复现

```powershell
# r1
python -I tools\run_holdout_paozhi.py --mode evidence --rounds 1
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261126.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json

# r3（开发配置）
python -I tools\run_holdout_paozhi.py --mode evidence --rounds 3
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261127_evidence_r3.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
```
