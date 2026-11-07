# 查询式交互（A/B/C + 共用底座）—— 交付与实测

> 会话日期：2026-10-13（承接 `项目接手总结-2026-10-12-收工版.md`）
> 用户本次授权原话：**「底座和 A/B/C 三入口一次性做完再交」**
> 本次**只新增文件**，未改动任何既有引擎/工具代码（`core/` 既有 5 个文件、`tools/` 既有脚本保持原样）。

---

## 〇、30 秒读完

* 交付两个新文件：`core/query_base.py`（底座 + 三入口的纯函数）、`tools/query_engine.py`（命令行）。
* **一次枚举 + 一份索引 + 三个入口**全部实测跑通；自检 **13 项 PASS / 0 FAIL**。
* 真实规模：甘草 12 个成分 / 煎煮 / 1 轮 → **552 个产物 / 552 条出处路径 / 4.13 s / InChIKey 552 成功 0 失败**。
  552 与 `predict_demo.py` 的 2026-10-12 实测数字**完全一致** → 说明底座用的就是当前默认完整档（配置 D）。
* 三条边界（查不到≠不存在 / 单分子只有单底物化学 / 新产物没有名字）已**写进每次输出**，不是只写在文档里。
* **排序/打分按你的决定停工**：score 只作为一列信息展示，不排序、不筛选。

---

## 一、怎么用（四条命令）

```powershell
$py = "D:\TCMAI\venv\Scripts\python.exe"; cd D:\ProgramData\DSHNS\chemreact-staging

# 底座：★一次枚举★（轮数由你掌握：--rounds N）-> 台账 CSV + 索引 TSV + 元信息 sidecar
& $py -u tools\query_engine.py build --herb 甘草 --limit 12 --rounds 1
& $py -u tools\query_engine.py build --smiles "OCc1ccccc1,NCCc1ccc(O)cc1" --rounds 2 --cond 醇提

# 入口 A 查产物：在不在 / 由哪条路径生成（第几轮、哪个来源分子、哪条规则）
& $py -u tools\query_engine.py A --mol "OCc1ccccc1"          # SMILES
& $py -u tools\query_engine.py A --mol "C7H6O2"              # 分子式
& $py -u tools\query_engine.py A --mol "XZGNQSXTIKZPJJ-RWHUPPPESA-N"   # InChIKey
& $py -u tools\query_engine.py A --mol "glycyrrhizin"        # 库里的名字

# 入口 B 查底物：只跑它 -> 产物（--with 再加一个 = 双分子反应）
& $py -u tools\query_engine.py B --mol "OCc1ccccc1" --top 20
& $py -u tools\query_engine.py B --mol "OCc1ccccc1" --with "NCCc1ccc(O)cc1"

# 入口 C 结果集检索：名称 / 分子式 / SMILES / 子结构（不高亮、不排序）
& $py -u tools\query_engine.py C --formula C9H6O3
& $py -u tools\query_engine.py C --substructure "c1ccccc1" --max-round 1 --top 30
& $py -u tools\query_engine.py C --name glycyrrhetinic
& $py -u tools\query_engine.py C --out reports\我的检索结果.csv --formula C9H6O3

# 入口 C+ 相似度检索（第三十轮新增；阈值默认 0.4）
& $py -u tools\query_engine.py C --similar "glycyrrhizin" --tanimoto 0.5 --top 20

# 聚合视图（第三十轮新增）：按反应类型汇总本次枚举
& $py -u tools\query_engine.py aggregate --top 40

# 查询日志汇总（第三十轮新增；A/B/C 默认记录，--no-log 可关）
& $py -u tools\query_engine.py stats

# 自检（换机器/换数据后复查；20 项判据）
& $py -u tools\query_engine.py selftest

# demo 也可以走同一个底座（验证两套路径口径一致）
& $py -u tools\predict_demo.py --herb 甘草 --limit 12 --via-base --top 10
```

**产物文件**（`build` 默认写这两个，都在 `reports/`）：

| 文件 | 内容 |
|---|---|
| `query_inventory_paths.csv` | **一行一条出处路径**：产物 SMILES / InChIKey / 分子式 / 来源分子 / 反应规则 / 第几轮 / 激活度 / 是否副产物 / score |
| `query_inventory_index.tsv` | **一行一个产物分子**：InChIKey / SMILES / 分子式 / MW / 重原子 / 来源数 / 路径数 / 最早轮次 / 规则列表 |
| `query_inchikey_cache.json` | InChIKey 缓存（可重复用；`--no-ik-cache` 可关） |

---

## 二、设计实现（对着你定的架构逐条对）

| 你定的 | 实现 |
|---|---|
| 一次枚举（产物带出处） | `query_base.build_inventory()`：每轮 `SmartReactEngine.step()`，path = (产物, 来源分子, 规则, 轮次, 激活度) |
| 一份索引（SMILES→InChIKey） | `Inventory.index()`：InChIKey → 条目（同一产物多个来源/多轮合并）；InChIKey 算不出时退化成 `SMI:<canonical>` 键，**并打印失败数** |
| 入口 A 查产物 | `query_product()`：输入 SMILES / 分子式 / InChIKey / 库内名称 → 命中则给**来源分子 → 规则 → 轮次**；SMILES 写法不同时自动走 InChIKey 回退 |
| 入口 B 查底物 | `query_substrate()` / `query_substrate_pair()`：只跑给定分子，**不走台账**（所以能查任何分子，包括不在台账里的） |
| 入口 C 结果集检索 | `query_inventory()`：名称 / 分子式 / SMILES / InChIKey / **子结构（SMARTS 或 SMILES）** / 轮次上限 / 是否含副产物；多条件取交集；**不排序、不高亮**（排序仅按"首次出现轮次 + SMILES"，且已在界面写明） |
| 轮数由用户掌握 | `--rounds N` 默认 1；**不设**自动收敛判据、**不设** `MIN_PROPAGATE_SCORE` 打分门槛替你截断 |
| 排序/打分停工 | score 仅一列信息；输出表里没有"推荐"、没有高亮 |
| 收敛问题变成用户可见信息 | 索引/清单里带 **`min_round`（该分子最早出现在第几轮）**，用户可以自己判断是级联炸出来的还是第 1 轮就有的 |

### 与既有代码的关系（先查有什么，再写）

* 枚举用 `SmartReactEngine`（**不重复实现**）；打分用 `scorer.score_product`；条件用 `conditions/templates.py` 的 10 个模板。
* **没有重新实现** `core/cascade.py` 的轮次逻辑——但故意**单列一份**：cascade 会自己按 `min_new` / `MIN_PROPAGATE_SCORE` 停，
  与"轮数由用户掌握"冲突，所以底座自己管轮次，`exclude_smiles` 语义与 cascade 完全一致（逐轮排除已出现分子）。
* 名称反查复用 `reports/coconut_inchikey_index.jsonl`（269,105 个 InChIKey）；子结构用 RDKit，不碰原子映射。

---

## 三、实测（全部为**实测**，口径已写死）

### 1. 自检 `selftest`（2 个底物 / 煎煮 / 1 轮）

| 判据 | 结果 |
|---|---|
| 底座：产物数 == 索引数 | PASS（12 == 12） |
| 底座：产物 > 0 / 出处路径 > 0 | PASS（12 / 12） |
| 索引：InChIKey 成功 12 / 失败 0 | PASS |
| A：抽 3 个真产物用 SMILES 查，命中 3 | PASS |
| A：按 InChIKey 查，命中 | PASS |
| A：三氟乙酸（不该有）→ `found=False` | PASS |
| B：单底物产物 3 个 / 双底物 12 个 | PASS |
| C：按分子式 C15H15NO3 查 4 个 / 子结构苯环查 8 个 / 不加过滤 == 全量 12 | PASS |
| C：按名称查（接通库） | PASS |

**合计 13 项，FAIL 0**（`tools\query_engine.py selftest`，exit 0）。

### 2. 真实规模：甘草 12 成分 / 煎煮 / 1 轮

| 项 | 实测值 |
|---|---|
| 产物分子 | **552** |
| 出处路径 | 552 |
| 枚举耗时 | **4.13 s**（引擎 3.24 s） |
| InChIKey | 成功 **552** / 失败 **0**（首次算，无缓存） |
| 被剔的"产物 == 输入分子" | 0 |
| 与 2026-10-12 `predict_demo.py` 的 552 对比 | **一致** → 底座 = 当前默认完整档（配置 D，能力基线 35.9%） |

入口实测（同一次台账）：

| 入口 | 输入 | 实测结果 |
|---|---|---|
| A | 台账里某产物 SMILES | 命中；`min_round=1`、1 个来源分子（Glycyrrhizic acid）、规则 `esterification`、激活 1.00 |
| A | 同一产物 InChIKey `XZGNQSXTIKZPJJ-RWHUPPPESA-N` | 命中（与 SMILES 同一条目） |
| A | 三氟乙酸 | `found=False`（正确） |
| A | 名称 `glycyrrhizin` | 库内解析到 5 个候选结构；**在产物集里 0 命中**（该结构本轮没被枚举出来） |
| B | 苯甲醇（单分子） | 产物 **2** 个，规则 `mined_mono`：苯甲醛（氧化）+ 一个环异构（激活 1.00，标"可逆"） |
| B | 苯甲醇 + 酪胺（双分子） | 产物 **7** 个 |
| C | 苯环子结构 | 命中 **358** 个 |
| C | `--formula C9H6O3` | 命中 1 个 |
| C | `--name glycyrrhetinic` | 库内 13 个候选结构；产物集里 **0 命中**，界面给出边界①提示 |
| C | `--name 甘草次酸`（中文名） | 库内 **0** 候选 → 说明 tcm.db 的 `compounds` 表**没有中文名列**（中文只在 `herbs.name_cn`） |

### 3. 多轮（`--rounds 2`，2 个底物）

`r1 新增 12 → r2 新增 154`，合计 **166 个产物 / 1.13 s**；InChIKey 命中缓存 12 个（复用 `query_inchikey_cache.json`）。
→ "轮数由用户掌握"这条链路可用，且第 2 轮的分子会带 `round=2` 标记。

### 4. 基线未被破坏（提交前必跑）

| 检查 | 结果 |
|---|---|
| `tools\audit_mapped_safety.py` | **ERROR 0**（WARN 12 个文件，与本次新增无关；mapped_chem 自检通过） |
| `test_conditions.py` | 20 通过 / 0 失败，exit 0 |
| `test_required_reagent_gate.py` / `test_condition_gate.py` / `test_solvent_gate.py` / `test_reagent_gate.py` | exit 0 |
| `verify_extra_templates_default.py` | 全部 PASS，exit 0 |
| `D:\TCMAI` 只读 | `tcm.db` / `coconut.db` 时间戳 2026-09-15 未变；`data\xtb_cache` 仍 **7** 个文件 |

---

## 四、本轮**顺手发现**的两个问题（都属你已认定的框架缺口，未擅自修）

1. **缺口②（方向性）又抓到一个实例**：
   甘草第 1 轮产物里 `XZGNQSXTIKZPJJ`（C84H122O31，MW 1627.9，115 重原子）经入口 A 溯源为
   **甘草酸 + 甘草酸**的 `esterification`，激活度 **1.00** ——
   水相 100 °C 里两个糖苷羧酸脱水成酯，方向可疑；而且它是**自抽单底物模板**（`mined_mono`），
   `activation=1.00` 是因为自抽模板不在 37 类条件表里、**绕过条件门控**（引擎既有行为）。
   → 这与"370 条水相酯化"是同一个洞，入口 A 现在能让用户**逐条看到**它从哪来，而不是被高亮蒙住。

2. **名称索引的边界被实测钉死**：
   * 中文名（甘草次酸）在 `tcm.db.compounds` 里**查不到**（该表只有 `name_en` / `alias`）；
   * `glycyrrhizin` / `glycyrrhetinic` 能在库里查到结构候选，但**它们没出现在本轮产物集里** ——
     界面会明说"库内候选 N 个，但结构没出现在本次枚举结果里"，这正是边界①。

**另外两条实现层的实测事实**（写下来省得以后重查）：

* `SmartReactEngine.step()` 的单底物模板**只对"参与过底物对"的分子生效**；
  底物对超过 `max_pairs` 时被截断的尾巴分子**不会被单底物模板覆盖**（本底座已把 `truncated` 打出来）。
* 引擎在 `exclude_smiles` 之外**不做**"产物 == 输入"剔除；底座补了这一步并计数（本次 0 条）。

---

## 五、边界与已知限制（有意为之，不是 bug）

1. **查不到 ≠ 不存在** —— 只等于"当前模板库 + 当前轮数没枚举出来"。枚举完整性是上限。
2. **入口 B 单分子只有单底物化学**；双分子必须 `--with` 给配体。
3. **新预测产物没有名字** —— 入口 C 的名称检索只对 tcm.db / COCONUT 里已有的分子有效；新结构请用 SMILES / 分子式 / 子结构查。
4. **产物清单不是判据**：候选预测（召回优先），score 只是信息列；"会不会发生"要看 `第二十七轮…报告.md` 的命中率口径。
5. **多轮会变慢且会膨胀**：非水介质缩合爆炸（缺口③）依然存在；底座不替你截断，所以 `--rounds` 别乱给大数
   （建议先用 1 轮看清产物，再决定加不加轮）。
6. InChIKey 用**子进程 + 25 s 超时**（RDKit 有过挂死实例）；超时的分子记入失败计数并打印样例，
   索引键退化为 `SMI:<smiles>`，**绝不静默丢弃**。
7. 台账是**纯文本 CSV/TSV**（没上数据库）：可复查、可用 Excel 打开；代价是几十万级规模时读回会慢
   （当前 552 条约 0.0 s；真要上百万再考虑 sqlite，属"多余的东西"，现在不做）。

---

## 六、我**没有**做的事（守住范围铁律）

* 没补任何场景层化学（水解/苷类/煎煮专用反应）—— 你没让做，铁律也不让做。
* 没动 scorer / 没有高亮 / 没有"推荐"。
* 没把 `core/thermo.py` 接进生产路径，没修缺口①（任意组分数）和缺口③（非水相不收敛）。
* 没动 `D:\TCMAI`，没动 `conditons/`、`core/` 里任何既有文件。

---

## 七、第二十九轮续：按你的优先级做的改进（2026-10-13，已实测）

> 你说的"先按这个顺序做"= ①#1 索引缓存 → ①#2 InChIKey 超时真保护 → ②1 来源分子带名字 → ②2 方向/平衡信号可见。
> 四条都做完了，**没碰化学口径、没碰场景层**。改完复跑：`selftest` **20 项 PASS / 0 FAIL**，
> `audit_mapped_safety` **ERROR 0**。

| 改动 | 前 | 后（实测） |
|---|---|---|
| **`by_smiles()` 缓存** | 每次调用重建整个索引（调用方在循环里查 → 二次方级慢） | 进程内建一次即缓存（`_smi2key`）；名称解析/子结构查不再重复重建 |
| **InChIKey 超时真保护** | 顺序 `fut.result(timeout=)`：一个分子挂死，后面全部干等；`shutdown` 杀不掉 worker | 整批一次提交 + `as_completed` + **单分子 25 s / 整批预算**双截止；超预算**kill worker**；放弃/超时分子**逐个记名打印**；`stat` 增 `timeout` / `abandoned` / `budget_s`；串行兜底也守预算 |
| **来源分子带名字+角色** | 出处只给 SMILES，你得自己认 | `label_of()`：先认"本次输入分子"（用输入名），再按 InChIKey 反查 COCONUT/tcm.db，**进程内缓存**；输出变 `[输入] Glycyrrhizic acid …` / `[中间体] …`；C 表新增「来源（首个）」列 |
| **方向/平衡信号可见** | `reversible` / `co_products` 只在内存里 | 台账 CSV 新增 `reversible` / `co_products`（同批生成片段）；索引 TSV 新增同两列；入口 A 命中时打印"⚠ 引擎标为可逆/介质相关（多半是平衡产物，别当终产物看）"+"同批生成的片段" |
| **台账自带元信息**（顺手补） | 读回台账时"枚举来源"显示"(读回)"，看不出条件/轮数 | 新增 sidecar `query_inventory_paths.meta.json`（条件/轮数/输入分子/逐轮统计/引擎档位）；读回后出处信息完整 |

**实测数字（改进后重建甘草台账）**：552 产物 / 552 路径 / **4.05 s**（InChIKey 552 全部命中缓存，0 失败）；
索引新列统计：`reversible=True` **552/552**（水相 + 全是缩合/自抽模板 → 全都不可传播，与引擎既有行为一致）、
`is_byproduct=True` **1 个**、`co_products` 非空 **537 个**。

**新暴露出来的两个观察**（不是 bug，是判读线索）：

1. 甘草第 1 轮 **552 个产物全部被标 reversible** —— 因为水相下"介质相关可逆性"把缩合类全标了可逆，
   加 `mined_mono` 的"判不了可逆性"也不传播。**含义**：这批产物在级联里一个都不会当中间体，
   所以"多轮"对水相基本不产生新东西；反过来，用户看到 reversible 标记就该知道"这是平衡物种"。
2. `co_products` 让"同批生成的片段"可见后，甘草酸自酯化那条（MW 1627.9）直接暴露出**它的 co-product 是自己** ——
   这正是缺口②（方向性）的可视化证据，入口 A 现在一次查询就能看到。

---

## 八、第三十轮：剩下四条也做完了（2026-10-13，用户「都做」）

| # | 新增 | 实现 | 实测 |
|---|---|---|---|
| ③ | **相似度检索** `C --similar` | `query_similar()`：Morgan(r=2, 2048bit) + Tanimoto；指纹表缓存 `query_fingerprints.json`（**带格式版本**，换算法自动失效）；一次 `BulkTanimotoSimilarity` 全量比完；按 InChIKey 去重；排序仅按相似度（**检索排序，不是替用户挑产物**） | 首次算 552 个指纹 **0.27 s**；查询 **0.09–0.56 s**；`glycyrrhizin` 阈值 0.35 → 484 个命中，最高 0.931 |
| ④ | **查询日志（证据回流）** `stats` | `dump_query_log()` / `stats_of_query_log()`：append-only JSONL，记录 时间/入口/查询/解析类型/命中与否/命中数；A、B、C、C+ 默认写，`--no-log` 可关，`--log-stats` 顺便看汇总 | 记录可用；汇总出命中率、按入口分布、查得最多的分子；**不排序、不推荐**，所以不违反"打分停工" |
| ⑤ | **按反应类型的聚合视图** `aggregate` | `aggregate_by_rule()`：每类反应的 产物分子数 / 出处路径数 / 来源分子数 / 最早轮次 / 占比 | 甘草 1 轮：`esterification` **370 产物 (67.0%)**、`mined_extra` 94 (17.0%)、`mined_mono` 88 (15.9%) —— 与可研报里"370 条水相酯化"**精确吻合** |
| ⑥ | **`predict_demo.py` 走共用底座** `--via-base` | demo 新增 `demo_via_base()`：枚举交给 `query_base.build_inventory`，demo 只显示（不再自己调 `engine.step()`）；旧路径保留可用 | 同输入走两套路径：**产物数一致（7 == 7）**、类型一致（`mined_mono`）；输出 `reports/demo_产物_共用底座.csv` |

**这一轮实测发现并修掉的 3 个性能/正确性问题**（都是先量后改，不是猜）：

1. **指纹算法选错**：旧式 `Chem.RDKFingerprint` 对 552 个天然产物（平均 106 重原子）要 **3.37 s**；
   换成 `rdFingerprintGenerator` 的 Morgan 只要 **0.06 s（快 50 倍）**。探针脚本：`tools\_probe_similar_cost.py`。
2. **查名字是隐藏瓶颈**：按 InChIKey 查 tcm.db 是**每分子一条无索引 SQL（≈26 ms/条）**，
   一次 484 命中的相似度检索光查名字就 **12 s**。改成一次性读入内存索引（29,013 个 InChIKey，0.05 s）后，
   同一查询 **10.9 s → 0.56 s**。探针脚本：`tools\_probe_similar_steps.py`。
3. **相似结果重复**：同一 InChIKey 的不同 SMILES 写法会连刷多行 → 加 InChIKey 去重。
   另外指纹缓存改成**只保存当前台账里的分子**，避免换台账后缓存无限膨胀。

**回归**：`query_engine.py selftest` **20 项 PASS / 0 FAIL**（新增 6 条：相似度检索/降序/无重复/上界、
聚合一致性、日志写入）；`audit_mapped_safety` **ERROR 0**；`test_conditions` 20/0；
`verify_extra_templates_default` 全部 PASS。

**新增的一键验证脚本**：`tools\_verify_round30.py`（相似度 / 聚合 / 日志三件事的摘要）。
两个一次性探针（`_probe_similar_cost.py` / `_probe_similar_steps.py`）保留下来，作为"为什么这么改"的证据。

---

## 九、下一步要你拍板的一件事

底座 + A/B/C 已按你的要求一次性做完并实测交付。**在你回答前我不写新代码、不跑新实验。**

要拍板的是：**接下来这一轮做什么？**

* 选项 1：**先验收这套交互**——你在真实问题上试用 A/B/C（比如拿一个你关心的分子查产物/当底物/检索），
  我按你的反馈改界面与字段，不动引擎。
* 选项 2：**回去补框架缺口②（方向性/热力学）**——它是"框架层"的洞，也正好是本次实测里
  甘草酸自酯化那类"能生成就生成"的根源；但要先定口径（哪些反应类型算可逆、用什么判据、`thermo.py` 怎么接）。
* 选项 3：**先补缺口①（任意组分数模板）**——影响 ORD 7.6% 的输入档，属通用性提升，但工程量大。

（我倾向先选项 1 再选项 2：交互是你验收过的东西，方向性才是真正的框架洞；但方向你比我有判断力。）
