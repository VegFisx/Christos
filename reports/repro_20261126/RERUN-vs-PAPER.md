# 论文数字与本机重跑对齐（2026-11-27）

目的：按用户要求，把论文里报告的每个基准数字用**当前工作树代码**重跑一遍，
确认论文数字 = 专家拿到仓库后实际跑出来的数字。

- 工作树：`D:\ProgramData\DSHNS\chemreact-staging`，HEAD `2635526`（重跑时工作树有未提交改动）
- 环境：Windows 11，CPython 3.12.10（`D:\TCMAI\venv`），RDKit 2026.03.6
- 调度：`_diag/run_remaining_detached.py`，逐步写 `status.json`，可断点续跑
- 结果目录：`reports/repro_20261126/results/`；日志：`reports/repro_20261126/*.log`
- 多进程：正向/逆向 4 workers，多步 4 workers

## 一、基准数字逐项核对

| 论文条目 | 论文值 | 2026-11-27 重跑 | 差异 | 结果文件 |
|---|---|---|---|---|
| 正向，基线（LEGACY+NO_EXTRA） | 55.53% | **55.53%**（0.5553，50,016 条） | 0 | `results/forward_50k__repro_baseline_mono_20261127.json` |
| 正向，当前默认（立体开） | 92.01%（46,020/50,016） | **92.01%**（0.9201，50,016 条） | 0 | `results/forward_50k__repro_default_20261126.json` |
| 正向，立体关 | 82.77%（41,398/50,016） | **82.77%**（0.8277，50,016 条） | 0 | `results/forward_50k__repro_stereooff_20261126.json` |
| 官方 test split，默认 | 91.71% / top-1 43.28%（4,993 条） | **91.71% / 43.28%**（top-5 67.75%，MRR 0.5496） | 0 | `results/forward_official_test__repro_official_default_20261126.json` |
| 官方 test split，生产口径 | 96.70% / top-1 73.30% / top-5 91.39% / 44.3 候选 | **96.70% / 73.30% / 91.39%**（4,993 条） | 0 | `results/forward_official_test__repro_production_20261126.json` |
| 逆向覆盖，5,002 目标 / 79,184 模板 | 94.74%（4,739/5,002） | **94.74%**（0.9474） | 0 | `results/coverage_summary__lib_uspto50k_excl_v2_s10.json` |
| 逆向覆盖，50,016 目标 / 3,065 模板 | 79.81%（39,919/50,016） | **79.81%**（0.7981） | 0 | `results/coverage_summary__lib_uspto50k_excl_s1.json` |
| 多步，深度 ≤2（路线找回） | 47.67%（143/300） | **47.67%**（143/300，928 s） | 0 | `reports/bench_multistep__repro_d2_20261126.json` |
| 多步，深度 ≤3（路线找回） | 72.33%（217/300） | **72.33%**（217/300，1,460 s） | 0 | `reports/bench_multistep__repro_d3_20261126.json` |
| 多步，至少一条完整可用路线，深度 ≤2 | 论文原未单列 | **47.33%**（142/300） | 新增 | 同上（逐目标 `n_usable`） |
| 多步，至少一条完整可用路线，深度 ≤3 | 207/300（69.0%） | **69.00%**（207/300） | 0 | 同上（逐目标 `n_usable`） |

结论：论文报告的 8 组基准数字全部逐位复现，无一处需要改数。

### 口径说明（多步）

`bench_multistep.py` 的 `ok` 是「是否找到至少一条路线」，不要求路线通过
`step_usability`；逐目标另有 `n_usable` 记录完整可用路线数。论文原先把
47.67%/72.33% 写成「成功率」，与同一段里「每一步都通过检查才算可用」的定义
冲突。2026-11-27 已改为分开报告：路线找回率 47.67%/72.33%，完整可用路线
47.33%/69.00%。代码与论文数字一致，只是标签更准确。

### 基线配置的坑

`CHEMCREACT_BENCH_LEGACY=1 CHEMCREACT_BENCH_NO_EXTRA=1 CHEMCREACT_BENCH_NO_MONO=1`
会得到 41.28%，**不是**论文的基线。论文基线是 `LEGACY+NO_EXTRA`、单模板层保持开启，
即 55.53%。REPRODUCE.md 里的命令已按后者写。

## 二、其它验证项的最近一次实测

这些不是 2026-11-27 重跑，而是 2026-11-24 至 11-27 期间同一工作树上的实测，
论文引用值均与结果文件一致：

| 项目 | 论文值 | 证据文件 |
|---|---|---|
| 规则用例 | 121/121 通过，111/111 规则覆盖 | `reports/reaction_cases_run_20261125.txt` |
| 炮制文献留出集 | 阳性 21 条：20 条骨架级命中（20/21，95.2%；THSG 全键一致，苍术苷仅骨架）；10 条负对照不计分。r3 开发配置：阳性 21/21，但负对照 9/10 也出产物 | `reports/holdout_paozhi_20261126.json` + `reports/holdout_paozhi_20261127_structure_supplement_20261127.json` + `reports/holdout_paozhi_20261127_evidence_r3.json` |
| 方剂库覆盖 v3（有出处口径） | 12,070 方 / 117,585 提及；解析 85.64%，完整解析 44.29%；歧义 2,541 不猜 | `reports/formula_db_coverage3_sourced_20261124.json` |
| 方剂端到端审计 | 20/20 跑通；中位 1,174 个候选产物（302–2,478）；40.5 s/方 | `reports/formula_end2end_20261125.md` |
| 甘草煎煮示例 | 2,176 条产物（`--limit 12 --rounds 1 --cond 煎煮`），208 s | `reports/repro_20261126/gc12/20261127-001322_甘草.meta.json` |

## 三、重跑耗时（本机，可作复现参考）

| 步骤 | 耗时 |
|---|---|
| 正向默认 / 立体关 / 基线 | 1,973 s / 1,955 s / 853 s |
| 官方 test 默认 / 生产口径 | 216 s / 约 1,000 s |
| 逆向 5,002 / 50,016 | 2,696 s / 2,413 s |
| 多步 d2 / d3 | 928 s / 1,460 s |

机器负载不同会浮动；数字本身是确定性的。
