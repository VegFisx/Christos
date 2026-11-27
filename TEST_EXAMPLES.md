# 测试样例（2026-11-27）

按“分钟级 → 几十分钟”的顺序排列。全部从仓库根目录运行。

## 1. 引擎 smoke：官方 test 前 150 条（约 20 秒）

```powershell
$env:CHEMCREACT_BENCH_LIMIT='150'
$env:CHEMCREACT_BENCH_OUT='out'
python -I tools\paper_bench_official_test.py 1
```

期望输出：

```
命中 133/150 = 88.67%  top1 48.67%  top5 68.67%  MRR 0.5836  平均候选 21.9  错误 0
```

它验证：依赖装好、`data/benchmark/uspto50k_official/raw_test.csv` 读得到、引擎能出候选。
注意 top-1 只是诊断，不是验收口径。

## 2. 规则/映射安全（约 1 分钟）

```powershell
python -I tools\audit_mapped_safety.py
```

期望：**ERROR 0**。它检查原子映射相关的危险写法，防止“静默得到空集”。

## 3. 31 条炮制留出集（几分钟）

```powershell
$env:CHEMCREACT_TCM_DB='data\tcm_holdout.db'
python -I tools\run_holdout_paozhi.py --mode evidence --rounds 1
python -I tools\score_holdout_presence.py reports\holdout_paozhi_20261127.json `
  reports\holdout_paozhi_20261127_structure_supplement_20261127.json
```

期望：

- 运行摘要：`23 consistent / 6 miss / 2 formula_only`；
- 存在性计分：`20/21` 骨架级命中，唯一阳性漏检是天麻素；
- 10 条负对照不计分，其中 5 条也出现了产物（已知的选择性诊断）。

如果日期不是 2026-11-27，把 `score_holdout_presence.py` 的第一个参数换成
`run_holdout_paozhi.py` 刚打印出来的那个文件。

## 4. 甘草 Demo（约几秒到几分钟）

```powershell
$env:CHEMCREACT_TCM_DB='data\tcm_subset.db'
python -I integration\tcmai_bridge\chemreact.py predict `
  --herb 甘草 --limit 1 --rounds 1 --cond 煎煮
```

期望：控制台打印产物数、台账路径和 HTML 报告路径；`--limit 1` 只为快速检查安装，
不用于复现论文的 2,176 条甘草台账。

## 5. 121 条反应级用例（需要完整 tcm.db，公开仓不完整）

```powershell
python -I tools\test_reaction_cases.py
```

期望（作者本机、完整 `tcm.db`）：**121/121 通过，111/111 规则覆盖**。

公开仓只带 17 味药和 56 个留出集化合物；这 121 条用例引用了 62 个 InChIKey，
公开子集只覆盖其中 32 个，所以这条命令在公开仓会报缺 key。它是内部回归测试，
不属于公开可复现路径；要用它，需要完整 `tcm.db`。

## 通过/不通过怎么读

| 现象 | 含义 |
|---|---|
| smoke 数字与上表不同 | 先确认 `data/benchmark/` 完整、没有设置 `CHEMCREACT_BENCH_*` 旧环境变量 |
| 留出集不是 23/6/2 | 确认 `CHEMCREACT_TCM_DB` 指向 `data\tcm_holdout.db` |
| 留出集 20/21 但负对照也出产物 | 预期行为；选择性是已知缺陷，论文和 `PUBLIC_REPRO.md` 都披露了 |
| 121 条用例报缺 key | 公开仓不含完整 `tcm.db`，属预期 |
