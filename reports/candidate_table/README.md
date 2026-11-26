# 候选级基准表（candidate table）

一句话：**11,996 个 USPTO 反应 / 257,444 个候选 / 59 维特征 / 真值**，落在一张 parquet 里；
载入 + 建特征 + 评估一次排序想法约 **1.7 秒**，不用再现搭数据集。

| 文件 | 大小 | 说明 |
|---|---|---|
| `candidates_v2.parquet` | 8.7 MB | 候选级主表（**未入 git**，用下面的命令重建） |
| `meta.json` | 4.5 KB | 列说明、特征顺序、`top_rules`、当前基线数字 |

```powershell
D:\TCMAI\venv\Scripts\python.exe -I -X utf8 tools\build_candidate_table.py   # 约 40 s
D:\TCMAI\venv\Scripts\python.exe -I -X utf8 tools\test_candidate_table.py    # 守约测试，须 0 失败
```

## 怎么用

```python
import sys
sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
import candidate_table as CT

df, meta = CT.load()                  # 0.4 s
X, names = CT.feature_matrix(df, meta)  # (257444, 59) float64，与 rank_model_v2.pkl 同口径
print(CT.evaluate(df))                # 发射序：top1=0.4706 top3=0.6599 top5=0.7392
print(CT.evaluate(df, score=X[:, 0])) # 换成任意分数（列名或等长数组）
print(CT.reaction_summary(df).head()) # 一行一个反应：split / want / n_cand / true_rank
```

## 表里有什么（47 列）

| 组 | 列 |
|---|---|
| 身份 | `rid` `split` `want`(真值) `rank`(发射序) `label`(1=命中) `smi` `sub` `rule` `tpl` |
| 引擎原始量 | `act` `sup` `eng` `ext` `cur` `byp` `prod_ha` `src_ha` `keep` |
| 29 维数值特征 | `rank` `log_sup` `act` `ext` `cur` `byp` `prod_ha` `src_ha` `keep` `p_*`(7) `s_*`(7) `d_*`(6) |
| 反应级 | `n_cand` `n_pos` `true_rank`（正例最小 rank，-1=未命中） |
| 反应元数据 | `uspto_id` `rxn_class` `r1` `r2` `src_join` |

30 个规则 one-hot **不存表里**，由 `meta["top_rules"]` 现做（避免 30 列稀疏宽表）；`feature_matrix` 已封装。

## 五条口径（比数之前先看）

1. **召回 ≠ top-1**：`recall_any = 0.9203`（真产物在候选里），`top1_emission = 0.4706`（排在第一位）。
   早先报告里的「发射序命中 92.00%」是前者。
2. **956 / 11,996 个反应没有正例**（`true_rank = -1`）。评估一律按 `n_pos > 0` 筛选，`evaluate` 已内置。
3. **必须 float64**。存 float32 会让模型分箱边界挪位，同一模型 top-1 从 0.7801 掉到 0.7754（实测）。
4. **MRR 是全序**。`train_ranker_v2.evaluate` 记录的 MRR 被截到 top-5（0.8684），同一批数据全序是 0.8702；
   两者不可直接比。
5. **split 按 `want` 的 md5 切**，与训练脚本同规则；可评测试反应 5,584 条。

## 边界

- 这是**快照**：规则 / 模板 / 引擎一变就要重建（40 s），不要拿旧表评新引擎。
- 只有 USPTO 12k 子集，**不含 TCM**；TCM 侧没有训练真值，别用它推断中药结果。
- 表里的 `tpl` 是挖掘模板 SMARTS，可用于按规则切片，但**不能**据此判断「会不会反应」（AGENTS §11.8）。
