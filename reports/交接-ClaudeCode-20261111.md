# 交接报告 · Christos（通用反应预测引擎）

> 写于 2026-11-11，交接给 Claude Code。目标：**接手的第一个小时就能跑起来、第二个小时就能改对地方**。
> 本文件自我包含，不需要读别的文档也能上手。但有两份必须通读：`D:\ProgramData\DSHNS\AGENTS.md`（工作规矩，16 节）和本文件第 3 节（不能碰的坑）。

---

## 0. 三十秒版

- **项目**：`D:\ProgramData\DSHNS\chemreact-staging`，一个本地运行的化学反应产物预测系统（品牌名 Christos / 炼膏师）。
- **做法**：从带原子映射的反应语料里挖模板（SMARTS），对底物枚举应用，得到候选产物；再用学习型重排序器排序。
- **状态**：v1.0.1 已发布到 <https://github.com/VegFisx/Christos>（MIT）。
- **头条数字**（全部可复现，见第 5 节）：
  - 召回 92.19%（官方 4,993 条可评）／**top-1 72.62%**（重排序 v2；不排序是 44.1%）
  - 逆向 94.74%、多步 47.67%（depth≤2）／72.33%（depth≤3）
  - 反应类型分层召回：常见 61.3% / 中等 31.8% / 稀有 6.0%（**这是架构的边界，见第 8 节**）
- **本地最新提交**：`4730005`（187 个提交），工作树干净。
- **远端**：`main = 5627d10`（"Christos 1.0.1"），标签 `1.0.1 → 1d9449f`。

---

## 1. 目录与关键文件

```
D:\ProgramData\DSHNS\                 ← 工作区根（AGENTS.md 在这里，不在 git 里）
  chemreact-staging\                  ← 主仓（git）
    core\                             ← 引擎：engine.py, smartreact_engine.py, query_base.py, rerank.py ...
    conditions\                       ← 条件层：model.py, activator.py, extent.py, kinetics.json, pressure.py, envelope.py
    rules\                            ← rules.json（71 条规则 / 12 个条件 profile）, paozhi_evidence.json（11 条炮制规则出处分级）
    sources\                          ← 数据访问：herb.py, formula.py, tcm_evidence.py
    integration\tcmai_bridge\         ← CLI（chemreact.py）+ 桌面壳（desktop.py）+ 界面（ui_page.html）
    tools\                            ← 100+ 脚本：基准、验证、挖掘、闸门
    reports\                          ← 论文、轮次报告、基准 JSON、模型 pkl、语料 jsonl
  tools\git.cmd                       ← 本机 git 包装（PATH 里没有 git，用这个）
  tools\release_push.ps1              ← 一键发布（快照仓 → 叠提交 → push → 打标签）
  _github_chemreact\                  ← 发布快照仓（不要手改，由 sync_publish2.py 刷）
  _rxnmapper_libs\                    ← RXNMapper 隔离安装目录（不动 venv）
  D:\TCMAI\                           ← 用户的中药库（**只读**，见第 3 节）
```

### 命令入口

```powershell
cd D:\ProgramData\DSHNS\chemreact-staging
$py = "D:\TCMAI\venv\Scripts\python.exe"

# 单味药预测
& $py integration\tcmai_bridge\chemreact.py predict --herb 甘草 --limit 6 --rounds 1 --cond 煎煮 --out out_dir --no-report

# 加候选重排序（v2，生产默认最优）
& $py integration\tcmai_bridge\chemreact.py predict --herb 甘草 --limit 6 --rounds 1 --cond 煎煮 --rerank --out out_dir --no-report

# 桌面应用
& "D:\TCMAI\venv\Scripts\pythonw.exe" integration\tcmai_bridge\desktop.py
```

---

## 2. 一次改动的标准流程（照做，不要发明）

```powershell
cd D:\ProgramData\DSHNS\chemreact-staging
$py = "D:\TCMAI\venv\Scripts\python.exe"
$g  = "D:\ProgramData\DSHNS\tools\git.cmd"

# 1) 语法检查（改过的每个 py）
& $py -c "import ast,io,sys; [ast.parse(io.open(p,encoding='utf-8').read()) for p in sys.argv[1:]]; print('AST OK')" core\xxx.py

# 2) 三套回归（秒级到十几秒）
& $py tools\audit_mapped_safety.py            # 必须 ERROR 0（原子映射安全）
& $py tools\test_audit_fixes_141.py           # 20 条断言，必须失败 0
& $py tools\test_pressure_p1.py               # 17 条
& $py tools\test_pressure_p2.py               # 26 条

# 3) 八场景烟雾（约 1 分钟）
& $py tools\run_paozhi_smoke.py               # 必须逐项等于 43/43/46/43/81/43/43/824

# 4) 涉及基准/排序的改动，跑发布闸门（约 9 分钟）
& $py tools\release_gate.py --profile quick --baseline reports\benchmarks\baseline-20261111.json

# 5) 提交
& $g add <files>; & $g commit -m "..." ; & $g log --oneline -1
```

闸门六步（`quick` 档）：safety / holdout / smoke / forward(600) / official(300) / multistep(50)。
阈值：召回跌幅 >0.003、official top-1 >0.005、multistep >0.05 判软退步；ERROR 非 0 判硬失败。
2026-11-11 基线：forward 86.59%、official 91.00% / top-1 41.67%、multistep 56%、holdout 3/6。

---

## 3. ★ 不能碰的东西与已知陷阱

### 数据与账号
- `D:\TCMAI\tcm.db`（63 MB）**只读**，且**爬虫可能正在写**：一律 `sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)`；**绝不删 `-wal`/`-shm`**。
- 不要动用户的 VS Code（里面有爬虫在跑）、不要读 `D:\TCMAI\data\formula_db.*`。

### 环境
- **venv 只有一个**：`D:\TCMAI\venv\Scripts\python.exe`（Python 3.12.10 + rdkit 2026.03.6）。`D:\TCMAI\.venv` 是死壳子。
- 本机**没有 pwsh**，只有 Windows PowerShell 5.1；含中文的 `.ps1` 必须存 **UTF-8 带 BOM**，否则报 `Unexpected token '}'`。
- **不要用 `python -c` 写含中文/引号的代码**（GBK 控制台会炸）。一律写 `_diag\xxx.py` 再跑。
- `Set-Content -Encoding UTF8` 会写 BOM，破坏 `ast.parse`；改文件用 `io.open(..., encoding='utf-8', newline='\n')`。
- `libs\` 在 `sys.path` 里排在前面，装包后要跑 `python tools\fix_libs_shadowing.py --apply`（老坑：rdkit 2024 遮蔽 2026）。

### 代码致命坑（都踩过，别重犯）
- **`canon_nomap()` 会抹掉原子映射号**：抹完再喂给依赖映射的逻辑会**静默**出错。一律用 `tools\mapped_chem.py`。
- **原子守恒必须含 `co_products`**，否则水解类全部误报。
- 判断「有没有立体」前先看生产读的是哪一列：`compounds` 表有两列，`smiles` 全平面，`isomeric_smiles` 才是带立体的，生产用 `COALESCE(isomeric_smiles, smiles)`（AGENTS §11.10）。
- `PATH_FIELDS` 是台账列的真源，加字段必须同时改 `core/query_base.py` 的 `PATH_FIELDS` 与路径字典，否则列永远空。
- 模板套用处有 3 处 `except Exception: continue`（`core/smartreact_engine.py`），会静默吞错，调试时先看计数器。

### 网络
- `github.com` 的 DNS 解析到不通的 IP，但 `api.github.com` 通。快照仓已设 `git config http.curloptResolve github.com:443:140.82.112.3`，之后 `push` 正常。
- `huggingface.co` 被墙，`hf-mirror.com` 通（`HF_ENDPOINT=https://hf-mirror.com`）。pypi 走清华镜像。

---

## 4. 架构（一句话一层）

```
语料（ORD/USPTO，带原子映射）
  → 挖掘模板（SMARTS，含条件 profile）        reports/mined_forward_templates_full_s5.jsonl（41,619 条）
  → 引擎枚举：模板 × 底物 → 候选产物 + 来路    core/smartreact_engine.py
  → 条件层：门控（会不会发生）+ 标注（进程）    conditions/activator.py, extent.py, pressure.py
  → 重排序：59 维特征 → HistGBM → 候选顺序    core/rerank.py + reports/rank_model_v2.pkl
  → 台账（每行带完整来路：输入→模板→轮次→底物） core/query_base.py（PATH_FIELDS 33 列）
```

**关键设计判断**（有实验依据，改动前先读第 8 节）：
- 条件**不决定产物身份**，只决定发生与程度。三次独立实验（包络筛 AUC 0.502、条件当特征 Δ=−0.11pp、条件感知模型生产 top-1 51.7% vs 68.2%）都支持这一点。
- 重排序是**唯一**能显著提升 top-1 的杠杆：42.5→66.9→72.6。
- 覆盖率的上限由语料类型覆盖决定，不由模板数量决定。

---

## 5. 基准怎么跑（口径必须一致）

```powershell
$py = "D:\TCMAI\venv\Scripts\python.exe"

# 正向全量（50,016 条）——立体默认开
& $py tools\paper_bench_50k_forward.py 100000 3

# 官方切分（4,993 条可评）+ 重排序 v2
$env:CHEMCREACT_BENCH_CLI_CONFIG="1"; $env:CHEMCREACT_BENCH_RERANK="1"
& $py tools\paper_bench_official_test.py 2

# 逆向（须编译模板库，否则掉 21 pp）
$env:CHEMCREACT_MS_TPL="reports/paper/data/lib_uspto50k_excl_v2_freq10.jsonl"
& $py tools\bench_multistep.py ...

# 反应类型分层
& $py tools\bench_class_strata.py --wide
```

**四组冻结数字不要混淆**（论文里有专门一节讲这个）：
| 数字 | 含义 |
|---|---|
| 91.69% | 论文冻结值（2026-10-19 那版代码） |
| 92.01% | 当前默认（立体开） |
| 92.19% | 官方 4,993 条子集口径 |
| 82.77% | 立体关（`CHEMCREACT_STEREO_CANON=0`） |

---

## 6. 数据与模型资产

| 文件 | 大小 | 说明 |
|---|---|---|
| `reports/paper/data/uspto50k_mapped.jsonl` | 21 MB | 5 万条 USPTO 经 RXNMapper 补映射（置信度中位 0.769） |
| `reports/center_dataset_uspto.jsonl` | 59 MB | 26,202 条可训练（置信度≥0.5）、269,978 个原子对 |
| `reports/rank_dataset_v2.jsonl` | 112 MB | 12,000 反应 / 257,444 候选 / 59 维特征（重排序训练集） |
| `reports/template_conditions.json` | 34 MB | 80,166 个模板的温时观测窗口（条件包络，**已判死但仍可当标注**） |
| `reports/rank_model_v2.pkl` | 0.7 MB | **生产用重排序模型**（59 维） |
| `reports/center_model_uspto.pkl` | 0.8 MB | 学习型中心模型（实验用，**不要接生产**，见第 8 节） |
| `reports/keep_model.pkl` | 0.7 MB | 原子存活模型（实验用） |
| `data/tcm_subset.db` | 2 MB | 脱敏中药子库（17 味药 / 2,899 成分），公开可用 |

大文件（>25 MB）不进 GitHub 发布集，但都在本地。

---

## 7. 当前状态：做完了什么

**已发布（v1.0.1）**
- 引擎 + 台账 + 条件层 + 重排序 + 桌面 GUI（中英双语，三个工作台：单味药 / 方剂 / 炮制）
- 论文中英双稿 + HTML + PDF（`reports/paper/arxiv-20261020/`）
- 四个基准族、发布闸门、十项测试

**最近三个月的主要改动**
- 立体化学默认开（+9.24 pp）
- 温度判据从「ORD 窗口」换成「规则自己的 profile 窗口」
- 条件层真正接线（A1 修复：以前 `--condition-extent` 是空操作）
- 压力 P1（表示层）+ P2（沸点上限截断）+ 浓度因子
- 重排序 v1（发射序 → 68.2%）→ v2（产物级 59 维 → **72.6%**）
- 数据层修复：丢 14.9% 边（LEFT JOIN）、小分子被 `LENGTH>3` 过滤、`CCO` 被当分子式
- 留出集（6 个预注册炮制案例，先提交预期再跑）+ 发布闸门

---

## 8. ★ 走过的死路（不要重走）

**每一条都有实测数字，报告在 `reports/` 里。**

| 方向 | 结论 | 关键数字 |
|---|---|---|
| 用条件包络筛产物 | 无区分度 | AUC 0.502（预注册阈值 0.6） |
| 条件当重排序特征 | 无增益 | Δ = −0.11 pp（规则族在场时） |
| 条件感知模型替代通用模型 | 更差 | 生产 top-1 51.7% vs 68.2% |
| 放宽模板环境（类比迁移） | 完全无效 | 命中 15/120 与放宽后 15/120，候选 ×1.7 |
| 同类反应迁移模板 | 零命中 | 0/265 |
| 扩池（2.3× 模板） | 只在中层有效 | 稀有层 12.5%→17.5%，但候选 ×14 |
| 中间档/最松档放宽 | 无效 | 稀有层 26→27，候选 +71% |
| **学习型键编辑生成** | **3.3% → 6.0%，判死** | 见 `reports/第一百五十轮-学习型路线结论-20261111.md` |
| 可疑产物检测器（D1） | 检测不到化学错误 | 严格重放 1,149/1,225 可复现，报警全是候选多样性 |

**学习型路线的教训（最重要的一条）**：
早先报出「单编辑 30.9%、并集 +4.0 pp」是**错的** —— 那个评测拿产物侧的原子映射号当白名单，等于把答案的原子集合交给了求解器。去掉后同一份代码只有 3.3%。
**规则：任何数字进结论前，必须先跑一遍「去掉自身最优假设」的对照。**

---

## 9. 还没做的（按价值排序）

1. **候选级基准表**（半天）：把 12,000 反应 / 257,444 候选 + 特征 + 真值落一张 parquet。以后任何想法都能 20 分钟出结果，不用现搭数据集。**这是最能减少「白忙一天」的一件事。**
2. **GitHub Release + Zenodo DOI**（需用户在网页操作）：基于标签 `1.0.1` 建 Release，拿 DOI 回填 `CITATION.cff` 与论文 Data availability。
3. 删远端 `auth-probe` 分支（`git push --delete` 被本机安全策略拦，需网页操作）。
4. **学习型结构化建模**（天级）：要把原子集合与编辑联合生成（图/序列生成），当前表示做不到。收益不确定。
5. 论文里 `--rerank` 仍是默认关（CLI 有开关、GUI 有勾选框），是否改默认为开要慎重：会改变所有既有数字。

---

## 10. 用户的工作方式（很重要）

- **每 5 轮左右停下来汇报**，等他拍板再继续。他说「做了吗」而不是「要不要做」时，是让你继续。
- 他**极度在意成本**（今天明说烧了 20 块）。汇报要压到 1/3 长度，不要复述已知信息。
- 他要求**不许编参数**：任何底层常数必须有文献或数据出处，没有就不做（AGENTS §十二）。
- 他知道自己在做什么：本仓库的很多数字（冻结基准、留出集、映射语料）是他盯出来的。**报数之前先自查**。

---

## 11. 第一个小时建议做什么

1. 跑一遍第 2 节的五步验证（大约 12 分钟），确认环境是好的。
2. 读 `reports/第一百五十轮-学习型路线结论-20261111.md` 和 `reports/第一百四十九轮-映射覆盖率与收率可行性-20261111.md`，理解当前的边界在哪。
3. 跑 `tools\release_gate.py --profile quick`，看一遍 `reports/benchmarks/` 里最新的成绩单。
4. 然后从第 9 节第 1 条开始 —— 那张基准表会决定后面所有工作的速度。
