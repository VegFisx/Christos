# 公开仓库能做什么、不能做什么（2026-11-27）

这份文件只回答一个问题：**专家从 GitHub 下载后，实际能跑出什么、不能跑出什么。**
论文正文与图件不在公开仓；公开仓是代码、规则、基准数据和可运行脚本。
具体可复制的测试样例见 `TEST_EXAMPLES.md`。

## 零、运行前提

- 从仓库根目录运行；Python 3.12.10。
- `pip install -r requirements.txt`；`rdchiral` 和 SmartReact 已放在 `libs/`，不需要额外安装。
- 下面是 Windows PowerShell 写法；bash 用户把 `$env:X='v'` 换成 `export X=v`，把反斜杠换成斜杠。

## 一、能独立复现的

| 能力 | 命令 | 期望 |
|---|---|---|
| 正向，50,016 条 | `python -I tools\paper_bench_50k_forward.py 100000 4` | 92.01%（立体关 82.77%，基线 55.53%） |
| 官方 test split | `python -I tools\paper_bench_official_test.py 2` | 91.71%（top-1 43.28% 仅诊断） |
| 逆向覆盖，5,002 | `python -I tools\paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl_v2.jsonl 10` | 94.74% |
| 逆向覆盖，50,016 | `python -I tools\paper_bench_50k_coverage.py 4 data/benchmark/lib_uspto50k_excl.jsonl 1` | 79.81% |
| 规则/映射安全检查 | `python -I tools\audit_mapped_safety.py` | ERROR 0 |
| 17 味药 Demo | `python -I integration\tcmai_bridge\chemreact.py predict --herb 甘草 --limit 1 --rounds 1 --cond 煎煮` | 可跑；自动回退到 `data/tcm_subset.db` |
| 31 条炮制留出集 | `$env:CHEMCREACT_TCM_DB='data\tcm_holdout.db'; python -I tools\run_holdout_paozhi.py --mode evidence --rounds 1` | 20/21 骨架级；r3 为 21/21 |

留出集的 20/21 需要用参考结构补充复核：

```powershell
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261127.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
# 20/21 skeleton-level hits, 1 positive miss, 10 negative controls
```

正向/官方/逆向所需的 USPTO-50k 目标、官方 test 文件、两个逆向模板库都已经在 `data/benchmark/`；模板池和 rank model 在 `reports/`。这些文件与作者本机重跑时使用的文件内容一致（忽略换行符差异）。

## 二、只能看、不能完整复现的

| 项目 | 缺什么 | 公开仓里有什么 |
|---|---|---|
| 多步 47.67% / 72.33% | ORD 派生的可购砌块索引（约 74 MB + 81 MB）、COCONUT 索引（15 MB）、完整 `tcm.db` 未随仓分发 | 模板库、脚本、结果 |
| 方剂覆盖 85.64% / 44.29% | `formula_db.json`（12,070 条方剂）未随仓分发 | 审计脚本、结果 |
| 方剂端到端 20/20 | 同上 | 审计脚本、结果 |
| 完整中医药层（31,646 成分） | 完整 `tcm.db` 未随仓分发；公开子集只有 17 味药、2,899 个成分 | `data/tcm_subset.db` |
| 论文正文/图件 | 按发布策略排除 | 无 |

## 三、专家能据此下什么结论

1. **反应引擎的头条数字可以独立验证**：正向 92.01%、逆向 94.74%/79.81% 都是用仓库里的数据跑出来的，不是只存在于论文里的数字。
2. **规则库可以审计**：117 条规则、每条的状态/出处/证据、41 条 ORD 数据证据、safety audit，都能直接查。
3. **中医药层：Demo 加留出集可复核，全量不可**：17 味药子集能跑通，31 条留出集能用 `data/tcm_holdout.db` 独立复核；但 31,646 成分、12,070 方剂的全量结论仍不能复核。
4. **多步与方剂覆盖数字不能独立复现**：缺的是上游数据，不是代码。

## 四、还需要补的缺口

**多步和方剂覆盖**仍然缺上游数据：多步需要 ORD 砌块索引（约 74 MB + 81 MB）和 COCONUT 索引（15 MB），方剂覆盖需要 `formula_db.json`（12,070 条）。是否公开要单独权衡体积与许可。

留出集的缺口已经补上：`data/tcm_holdout.db` 只含 56 个 seed/target 和 739 味关联药材（约 524 KB），由 `tools/build_tcm_holdout_subset.py` 从完整 `tcm.db` 只读抽取，不替代完整库。
