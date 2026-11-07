# 第七十五轮 · B10 fig3 口径核查

> 目的：解释 `fig3_coverage_topk` 的 94.7% 与 B10 复现的 79.81% 为何不同，确认论文图应该用哪一套。
> 只读比较，不改论文图；候选图另存到 `reports\paper\figures_b10_check\`。

## 一、两套结果的关键字段

| 口径 | n_targets | 库 | 库模板数 | any-hit | top1 | top3 | top5 | top10 | top50 |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 主线 `coverage_summary.json` | 5002 | lib_uspto50k_excl_v2.jsonl | 79184 | 94.74% | 15.07% | 27.21% | 33.61% | 43.36% | 68.65% |
| B10 `coverage_summary__lib_uspto50k_excl_s1.json` | 50016 | lib_uspto50k_excl.jsonl | 3065 | 79.81% | 16.18% | 29.08% | 35.67% | 44.40% | 65.79% |

## 二、结论

* 主线 any-hit **94.74%** 的分母是 **5,002 个目标**，库是 `lib_uspto50k_excl_v2.jsonl`（**79,184** 条模板）；
* B10 any-hit **79.81%** 的分母是 **50,016 个目标**，库是 `lib_uspto50k_excl.jsonl`（**3,065** 条模板）。
* 两者既不是同一目标集，也不是同一模板库；**94.7% 不能当作“USPTO-50k 全量 + 泄漏剔除库”的覆盖率**。论文 fig3 若标注 USPTO-50k，应使用 B10 这套 50,016 目标 / 3,065 模板的 79.81%。
* 这不是脚本算错，而是 `paper_make_figures.py::fig3()` 默认读主线 `coverage_summary.json` 造成的口径错配。

## 三、建议

1. A4 已把 fig3 的数据源改为 B10 的 `coverage_summary__lib_uspto50k_excl_s1.json`；
2. 主图已重跑为 79.8%；旧 94.7% 图保留在 `figures.before-b10-rerun/`；
3. 若论文正文要保留 94.7%，必须把图注/正文改成“5,002 目标 + v2 库”，不能写 USPTO-50k 全量。

## 三b、A4 已执行的决定（2026-10-17）

* **USPTO-50k 全量图采用 B10 口径 79.81%**（50,016 目标 / 3,065 模板）；
* `tools/paper_make_figures.py::fig3()` 已改为优先读
  `coverage_summary__lib_uspto50k_excl_s1.json`；
* 主图 `reports/paper/figures/fig3_coverage_topk.png` 已重跑为 79.8%；
  旧 94.7% 图保留在 `reports/paper/figures.before-b10-rerun/`；
* 94.7% 仅作为“5,002 目标 + v2 库”口径备查，不再作为 USPTO-50k 全量图。

## 四、复现

```powershell
cd D:\ProgramData\DSHNS\chemreact-staging
& D:\TCMAI\venv\Scripts\python.exe -u tools\check_b10_fig3_scope.py
```

已写候选图：D:\ProgramData\DSHNS\chemreact-staging\reports\paper\figures_b10_check\fig3_coverage_topk_b10.png
