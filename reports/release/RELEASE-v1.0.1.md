# Christos（炼膏师）· 发布说明 V1.0.1（2026-10-16）

> 产品名：**Christos（炼膏师）**；内部包名/命令仍为 `chemreact`。

> **V1.0.0 冻结物一律不动**（软著三件套与论文基线仍指向 V1.0.0）。
> 本版是**资源/复现包的增补版**：把第七十四~七十五轮的新数据、新脚本与新报告打进来。

## 一、相比 V1.0.0 增补了什么

| 类别 | 新增 |
|---|---|
| **数据（`data/`）** | 方剂出处分档 `formula_source_tier.json`（12,071 条）；AI 古方抽检判定 `h2_verdicts_all.json`（n=300）+ 两批抽样清单；验收用例来源台账 `case_sources.json`；药典成方制剂 `chp_formulas.json`（1,526）；炮制品闸 `chp_processed.json`（20）；中文药名→物种 `herb_species.json`（547）；多候选别名索引 `alias_index.json`（31,440 别名）；药典剩 4 味查证 `gap4_findings.json`；**补库补丁包** `patch_missing_herbs/`（52 味：明细 + patch/rollback SQL + README） |
| **脚本（`scripts/`）** | 出处分档生成、用例数据库化、H2 判定/合并/报告、补库补丁生成、药材名口径检查、**离线回归套件** `run_regression_suite.py`、软著手册生成器 |
| **文档（`docs/`）** | 第七十五轮系列报告（数据出处隐患 / AI 古方抽检 / 用例 DB 化前后 / 回归自查 / 复现演练 B10 / 别名缺口与药典剩 4 味）；软著手册提交版 |

## 二、能力数字（与 V1.0.0 相同，未改口径）

正向单步召回 **82.32%**（泄漏剔除版，CI 81.99–82.66）；逆向覆盖率 **94.74%**（全量）/91.90%（freq10）；
多步端到端 **47.7%(d≤2) / 72.3%(d≤3)**（n=300）；药典判据链覆盖 **386/491**。
**生产默认未变**（正向 extra≥10/20k + mono 6k + cap32 + prefilter；逆向 freq10 + 黑名单默认关；`--chp-priority` 默认关）。

## 三、内容清单

* `chemreact-v1.0.1-pack.zip`（64 文件 / 17.8 MB）
* `sha256_manifest_v1.0.1.txt`（56 条，覆盖 240.5 MB：库、判据表、结果、脚本、软件文档）
* 校验：`python tools\make_release_pack.py v1.0.1` / `python tools\make_snapshot_manifest.py v1.0.1` 可整包再生。

## 四、本轮新增的"可判定"入口（验收用）

```powershell
python tools\run_regression_suite.py         # 离线回归套件（13 个脚本，梯子不通也能跑）
python sources\formula_source.py             # 出处分档分布自检
python tools\check_tier_filter.py            # 网页「按出处筛看」是否真生效（node 跑渲染函数本体）
python tools\check_herb_naming.py            # 药材名口径（HERB 本名/别名，4 条）
python tools\verify_case_conversion.py       # 用例数据库化"无偷换"
python tools\h2_merge.py && python tools\h2_report.py   # H2 抽检合并与报告再生
```

## 五、已知边界（与 V1.0.0 相同，另加两条）

* 抽检只覆盖**固定种子抽中的 300 条**；未抽中的版本在网页上显示「未抽检」（不代表有问题）；
* 别名广域缺口（5,982 个库外规范名）**尚无"中文→物种"源**：本地三源都不行，Wikidata 信道因网络超时**未测成**（见 `docs\第七十五轮-别名缺口与药典剩4味.md`）。
