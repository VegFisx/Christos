# 数据卡（DATA CARD）

> 论文/复现包的数据清单：来源、版本、许可、生成方式、已知限制。
> 2026-10-18 已完成 COCONUT、USPTO-50k、retrosim、SmartReact 的官方许可核验；
> 2026-10-29 已补核 TDC、CTD、Tox21/ToxCast、OnSIDES 和药典 2025 的来源；
> 原始响应快照见 `reports/paper/reference_verification_20261029/`。
> 仍标 **[待核]** 的事项只剩需要库主/维护者授权或第三方出版物条款的项目。

## 1. 反应模板的原始数据

| 项 | 内容 |
|---|---|
| 名称 | ORD（Open Reaction Database）· 数据集 `uspto-grants` |
| 文件 | `ord-data/data/11/ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet`（约 1.11 GB，1,771,032 条） |
| 来源 | ORD 公开仓库的本地克隆（`ord-data/`；含 LICENSE 与 `retired_datasets.csv` 溯源：由 `uspto-grants-1976_XX` 系列合并而来） |
| 许可 | cc-by-sa-4.0（`ord-data/README.md` 首页声明） |
| 我们用到多少 | 前 60,000 行（10 片 × 6,000，offset 0~54,000；`reports/_shard_*.log` 可核）→ 56,047 条成功抽取 |
| 生成脚本 | `tools/retro_extract_shard.py`（rdchiral 模板抽取）→ `tools/retro_cluster_eval.py`（合并/聚类） |

## 2. 基准目标集

| 项 | 内容 |
|---|---|
| 名称 | USPTO-50k（"Chemical reactions from US patents" 的常用精选子集） |
| 版本/镜像 | `connorcoley/retrosim` 仓库的 `data/data_processed.csv`（50,016 行，10 类标签） |
| 原始出处 | Schneider, Stiefl, Landrum. *What's What: The (Nearly) Definitive Guide to Reaction Role Assignment.* J. Chem. Inf. Model. 2016（[10.1021/acs.jcim.6b00564](https://doi.org/10.1021/acs.jcim.6b00564)）；底层为 Lowe 的 USPTO 2016 抽取集（figshare 5104873） |
| 许可 | **figshare 5104873 = CC0**；**`connorcoley/retrosim` 代码 = MIT**（2026-10-18 官方 API 实测；证据见 `reports\_network_evidence_20261018\`） |
| 我们的处理 | 去映射号规范化（`tools/paper_50k_prep.py`）→ `uspto50k_canon.jsonl`（50,016 条，0 失败） |

## 3. 终止集合（搜索用"买得到"的近似）

| 组成 | 数量 | 来源/许可 |
|---|---|---|
| COCONUT（天然产物库） | 269,105 有效分子（InChIKey 索引 272,992 条原始） | `D:\TCMAI\coconut.db`（用户本地未标版本的快照）；COCONUT 官方 Download/About 页明确 **curated dataset = CC0**，代码 MIT；证据见 `reports\_network_evidence_20261018\` |
| tcm.db（中药成分） | 31,646 | 用户自建（本地，只读访问 `tools/tcm_ro.py`） |
| 可购砌块（ORD 反推） | 32,146 full key + 30,236 skeleton | 由 §1 同源 ORD 数据生成（`tools/build_purchasable_blocks.py`）；继承 cc-by-sa-4.0 |

**已知限制**：COCONUT 中"存在" ≠ 现实可购；砌块表是商业可得性的代理，终止判定系统性偏乐观（论文须声明）。

## 4. 软件依赖（锁版本）

| 软件 | 版本 | 位置 |
|---|---|---|
| RDKit | 2026.3.6 | `D:\TCMAI\venv`（Python 3.12.6；本轮实测） |
| rdchiral | 1.1.0 | `chemreact-staging/libs/`；**MIT**（本地 `dist-info/LICENSE`） |
| duckdb | 1.5.6 | 仅 3.12 环境（venv）里用；**MIT**（本地 `dist-info/licenses/LICENSE`） |
| ord_schema | 0.8.3 | 同上 |
| matplotlib / seaborn | 3.11.2 / 0.13.2 | venv（画图） |

## 5. 下游毒性与疾病数据源

这些来源用于下游风险标注或覆盖审计，不参与正/逆合成模板的生成。

| 数据源 | 本地使用 | 引用 | 许可与状态 |
|---|---|---|---|
| TDC ADMET Group | `D:\TCMAI\data\admet_cache.db`，23,405 个 InChIKey；含 `LD50_Zhu`、`hERG`、`DILI`、`AMES`、`ClinTox`、`Carcinogens_Lagunin` 等 TDC 端点 | Huang et al. 2022, *Nature Chemical Biology* 18(10):1033–1036, [10.1038/s41589-022-01131-2](https://doi.org/10.1038/s41589-022-01131-2)；数据接口：[TDC ADMET Group](https://tdcommons.ai/benchmark/admet_group/overview/) | TDC 软件代码为 MIT；各数据集保留上游许可，不能用一个总许可证覆盖。原始数据不随本项目分发。 |
| Tox21 / ToxCast | 同一 ADMET cache 中的 `NR-*` 与 `SR-*` 通路端点 | Richard et al. 2021, *Chemical Research in Toxicology* 34(2):189–216, [10.1021/acs.chemrestox.0c00264](https://doi.org/10.1021/acs.chemrestox.0c00264)；Richard et al. 2016, *Chemical Research in Toxicology* 29(8):1225–1251, [10.1021/acs.chemrestox.6b00135](https://doi.org/10.1021/acs.chemrestox.6b00135)；项目页：[US EPA Tox21](https://www.epa.gov/chemical-research/toxicology-testing-21st-century-tox21) | 公开研究数据；原始记录不随本项目分发。 |
| CTD | `data/CTD_chemicals_diseases.csv.gz`；2026-10-27 下载，审计扫描 9,903,450 行；按化学名连接 | Davis et al. 2026, *Nucleic Acids Research*, “Comparative Toxicogenomics Database: update 2027”, [10.1093/nar/gkag1041](https://doi.org/10.1093/nar/gkag1041) | 文件头声明使用须遵守 CTD 法律条款并引用 CTD；原始文件仅本地保留、不随本项目分发。 |
| OnSIDES | `data/onsides/` 与 `data/onsides-v3.1.1.zip`；当前用于下游数据准备，未进入本文头条结果 | Tanaka et al. 2025, *Med* 6(7):100642, [10.1016/j.medj.2025.100642](https://doi.org/10.1016/j.medj.2025.100642)；数据版本：[OnSIDES v3.1.1](https://github.com/tatonetti-lab/onsides/releases/tag/v3.1.1) | GitHub 仓库为 MIT；原始标签/ADE 数据不随本项目分发。 |
| 中国药典 2025 | `chp_formulas.json`、`chp_processed.json`、`herb_species.json` 的法定条目字段 | 国家药典委员会《中华人民共和国药典（2025 年版）》，北京：中国医药科技出版社；结构化来源：[Independent-KBs](https://github.com/cliviali/Independent-KBs)，核验提交 `63cfd6a` | 官方标准与第三方结构化版均不随本项目分发。第三方仓库未声明仓库级许可证，因此只能内部使用，不能把“可访问”解释为“可再分发”。 |

**来源边界（实测）：**

1. `admet_cache.db` 只有 `inchikey` 与 JSON 字段，未保存 TDC 发布标签；可按字段确认属于 TDC ADMET Group，但**精确导出日期不可考**，论文须写“TDC-derived cached snapshot”，不能伪造版本号。
2. Tox21/ToxCast 端点来自同一缓存；没有独立原始数据文件，因此同样只能声明数据谱系，不能声明本地数据版本。
3. CTD 与 OnSIDES 原始文件仍受各自条款约束，不进入公开演示包。

## 6. 第七十四~七十五轮新增的数据产物（TCM/中药侧；全部脚本生成、可复算）

> 这些是本软件**自己的产出**（写在 `chemreact-staging\data\`），不进用户的数据库；
> 生成方式与验收证据见 `reports\第七十五轮-数据出处隐患.md`。

| 文件 | 内容 | 来源（输入） | 生成脚本 |
|---|---|---|---|
| `chp_formulas.json` | 药典 2025 成方制剂 **1,526** 条（组成 + 法定剂量 + 功能主治 + 官方 URL） | 药典 2025 知识库（第三方结构化版，条目带 ouryao URL） | `tools\build_chp_formulas.py` |
| `chp_processed.json` | 药典收载**炮制品 20 味**（含基原；供"禁止替换"闸） | 同上（名录 + 炮制标记 + **同物种**双判据） | `tools\build_chp_processed.py` |
| `herb_species.json` | 中文药名 → 拉丁学名/COCONUT 物种（617 味里 547 条） | 药典正文拉丁学名 + COCONUT 种名字典 | `tools\build_herb_species.py` |
| `alias_index.json` | 多候选别名索引 **31,440** 别名（5,417 多候选，带辞典出处） | 用户自有 NTU《中文药名同义词表》（50,607 行）+ `tcm.db` | `tools\build_alias_index.py` |
| `formula_source_tier.json` | 方剂逐条**出处分档**（12,071 条：药典（2020 英文导入）/ ETCM / ITCM / CPMCP / 古籍 / AI 现查（未核对）；2025 中文法定版另由 `chp_formulas.json` 提供） | `formula_db.json`（用户库，只读）+ 药典 overlay | `tools\build_formula_source_tier.py` |
| `h2_verdicts_all.json` | AI 现查古方**抽检判定** n=300（命中 28.0% / 部分命中 66.3% / 查无 5.7%，含来源链接） | 固定种子抽样 + 公开来源检索（证据留存 `reports\_h2_net*`） | `tools\h2_verdicts2.py` + `h2_merge.py` |
| `case_sources.json` | 验收用例分子来源台账（86 处数据库引用 / 43 处库外字面量） | `tcm.db`（只读）+ 归档的手写用例 | `tools\build_cases_from_db.py` |
| `patch_missing_herbs\` | **补库补丁包**（药典缺 52 味：明细 + patch/rollback SQL + README） | 药典知识库 + `herb_species.json` | `tools\build_missing_herbs_patch.py` |
| `gap4_findings.json` | 药典"真缺口"最后 4 味的核对结论 | `tcm.db` + `coconut.db`（只读） | `tools\check_gap4.py` |

**已知限制（诚实声明）**：

1. 出处分档里 **AI 现查（未核对）**（5,332 条）是**来源标签**，不是"错"；抽检显示 94.3% 能核到同名方、
   28.0% 组成逐字一致，**其余是同名不同版本**；
2. 抽检只覆盖固定种子抽中的 300 条；未抽中的版本在界面上显示"未抽检"；
3. 别名广域缺口（5,982 个库外规范名）没有一次性全部解决；Wikidata 信道已在网络恢复后复核，
   当前 `alias_species_bridge.json` 有 336 个优先名，其中 106 个落到分类单元、73 个落到 COCONUT 物种；
   该桥必须有“实体中文标签 == 查询名”约束，不能自动接受模糊匹配（见
   `第七十五轮-别名缺口与药典剩4味.md`）；
4. 补库补丁**只含药材元数据，不含成分数据**；成分仍走"药典拉丁学名→COCONUT 物种"兜底。

## 7. 本项目内产出的中间件（可再生成）

* `reports/_shard_[0-9].jsonl`（56,047 条抽取记录，每条含完整映射反应 `rx`）
* `reports/retro_templates_clustered.jsonl`（生产库 3,228 = 复现校验对象）
* `reports/paper/data/lib_uspto50k_excl.jsonl`（基准库 3,065，泄漏受控）
* `reports/retro_template_sources.jsonl`（模板 -> ORD reaction_id 出处表；3,228/3,228 覆盖）
* `reports/retro_template_blacklist.json`（51+3+3 名单，带留出豁免证据）
* `reports/paper/results/*`（覆盖率、可用性、稳定性结果）

## 8. 合规与再分发

* **我们在论文/仓库中不分发** ORD/COCONUT/USPTO-50k 的原始数据；只分发脚本与"由公开数据生成的模板/清单"，
  并注明上游出处与许可。ORD 衍生模板按 **CC BY-SA 4.0** 处理；USPTO-50k 为 **CC0**；
  COCONUT 上游数据为 **CC0**；SmartReact 模板包为 **Apache-2.0**。
* 用于评测的 50k 记录不进入也不来自任何一份中间产物（由 §协议 的剔除流程保证）。
