# 第十七轮 · ORD 条件 + 数值收率训练表

数据源：`chemreact-staging\ord-data\data\11\ord_dataset-1158e351757f315b93cbcbe7bc55f38e.parquet`
（uspto-grants，1,771,032 条；**只读，未改动 ord-data 目录**）

## 交付物

| 文件 | 说明 |
|---|---|
| `chemreact-staging\tools\ord_condition_dataset.py` | 抽取脚本（argparse：`--limit` `--out` `--seed` `--resume`，另加 `--workers` `--shard-rows` `--max-shards` `--show-raw` `--summary-only`） |
| `chemreact-staging\reports\ord_condition_dataset\shard_0000..0177.parquet` | 178 个分片，**925,943 行**，157.9 MB（+ 同名 `.stats.json`） |
| `chemreact-staging\reports\ord_condition_dataset_summary.json` | 汇总（口径计数、分布、失败分类、分片校验） |
| 本报告 | — |

## 一、口径（写死，见脚本头部注释）

一条记录入表 ⟺ ①有 `REACTION_CXSMILES` 且能拆 底物>试剂>产物；②产物侧 SMILES 可被 RDKit 解析；
③存在 `outcomes.products.measurements` 满足 `type==YIELD` **且 `HasField('percentage')`** 且 `0<value<=100`。
`yield_percent` 取值优先级（**小样本实测后定死**）：`PERCENTYIELD`（论文原文）> `CALCULATEDPERCENTYIELD` > 其它 details 中最大类；同 details 多值取最大（多产物 → 主产物）。
只取结构化字段，**不做文本正则抽收率**（`notes.procedure_details` 里的收率不算）。

## 二、小样本实测【实测】`--limit 5000 --seed 20261013`（duckdb reservoir，6.0s 抽样）

| 指标 | 数值 |
|---|---|
| 处理 5,000 条 → 入表 | **2,597 行（51.94%）** |
| `fail_no_yield_measurement` | 2,310（46.20%，收率只存在于正文文本） |
| `fail_yield_out_of_range` | 92（1.84%） |
| `fail_product_unparsable` | 1；protobuf/CXSMILES/无产物 = 0 |
| 温度 / 溶剂 / 催化剂 可得率 | 28.07% / 85.25% / 16.63%（reagent 0%） |
| reaction_class | 0 / 2,597（本数据集完全没有） |

## 三、全量结果【实测】

- **job id `pwsh-1322`（后台，`--resume --workers 6`）— 已 100% 完成**：178/178 分片，0 失败，
  1,771,032/1,771,032 条，耗时 **141.0s**（12,275 条/s）。
- 入表 **925,943 行 = HTE(27,497) 的 33.7 倍**，占已处理 52.28%。
- 失败分类：`fail_no_yield_measurement` 806,564（45.54%）；`fail_yield_out_of_range` 38,430（2.17%）；
  `fail_product_unparsable` 95；protobuf / 无 CXSMILES / 拆段 / 无产物 = 0。
- 可得率：温度 28.46%、溶剂 86.13%、催化剂 16.51%、试剂 0%、DOI/专利 100%、反应时间 55.79%、
  reaction_class **0%（0 种）** —— 该 parquet 的标识类型统计 100% 是 `REACTION_CXSMILES`，
  `provenance.reaction_metadata` 全空（【实测】，非解析漏读）。
- 温度分布（分母=有温度的 263,560 行）：≤0 ℃ 24.29%、0-25 9.27%、25-50 10.66%、50-80 24.30%、
  80-120 22.79%、120-200 8.27%、>200 0.42%；单位 CELSIUS 263,550 / FAHRENHEIT 9 / KELVIN 1（已换算）。
- yield 分布：0-10 2.46% … 80-90 15.83%、90-100 18.08%（右偏，符合文献收率习惯）。
- 独立校验：直接读 178 个分片 footer 合计 925,943 行 = stats 合计，`rows_match=true`，0 片不一致，无残留 `.tmp`。

## 四、踩到的坑【实测】

1. **`CALCULATEDPERCENTYIELD` 有垃圾值**：1059 对里 191 对完全相等、465 对差 <0.5（四舍五入），
   但 171 对差 ≥5，最大差 98,195（出现 73,011% / 98,293% / 80,000%）。故口径改为**优先 PERCENTYIELD**，
   否则“取最大”会被污染；改后 `yield_inconsistent` 从 41.3% 降到 15.4%（小样本）。
2. **`inputs` 的 key 是 `m1_m2` 这种不透明串**，角色只能从 `components[*].reaction_role` 读；
   `reaction_role` 只出现 REACTANT/SOLVENT/CATALYST（**没有 REAGENT**），故 reagents 列全空。
3. **`ord_schema` 的枚举不能直接 `Name()`**：`R.ReactionRole` 在本环境是 message 不是枚举包装器
   （`AttributeError: Name`），改用 field descriptor 的 `enum_type.values_by_name` 反查。
4. **温度 0.0 不是占位符**：40,421 行（4.37%）setpoint=0 ℃，抽 3 条看 `procedure_details` 原文
   是 “chilled to 0° C”（冰浴），故保留并单列 `temperature_zero` 标记。
5. `yield_out_of_range` 分档：100<v≤130 有 42,522 个、v>130 有 27,528 个、≤0 有 809 个 ——
   轻微 >100% 属论文常见写法，故仅单值剔除，只要记录里还有合格值就仍入表。
6. RDKit 对非法价态会往 stderr 刷 “Explicit valence…” 噪音（对应 95 条 `fail_product_unparsable`），
   已 `RDLogger.DisableLog`，避免淹没失败统计。

## 五、限制与下游建议

- **没有 reaction_class 可直接用**（【实测】0 种）。要做“条件感知判据”的分组，需另找分组键：
  建议用已有 `tools/forward_template_mining.py` 的反应中心/模板，或按 reactants–product 组成聚类。
- 温度只有 28.46%，是本表最稀缺的条件维度；`temperature_C` 缺失时不要当 0 处理。
- 建议下游按 `yield_source_details == 'PERCENTYIELD'` 优先、并用 `|yield_percent - yield_alt_percent| > 0.5`
  过滤掉 `yield_inconsistent` 的 15.40% 行。
- 分片读取用 duckdb：`read_parquet('reports/ord_condition_dataset/shard_*.parquet')`；重跑加 `--resume` 即续跑。
