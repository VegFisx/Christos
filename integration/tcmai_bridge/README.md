# Christos（炼膏师）· TCMAI 桥接

> 产品名：**Christos（炼膏师）**；内部包名/命令仍为 `chemreact`，本文命令中的
> `chemreact.py`、`chemreact-staging` 是历史路径，不是产品名。

把 **chemreact-staging** 里的通用化学 AI（正向枚举 + 逆合成 + 方向/条件标注）接到 TCMAI 项目里的入口。

## 是什么 / 不是什么

* **是**：一个薄桥接（`chemreact.py`）——TCMAI 侧可以直接跑的命令行；引擎源码仍在
  `D:\ProgramData\DSHNS\chemreact-staging`（**单一来源**，这里不复制代码，升级引擎不用改这边）。
* **不是**：不往 tcm.db / coconut.db 写任何东西（全程只读连接）；不含煎煮专用化学——
  条件层目前只做"打标记"，等框架完成后再补场景层。

## 快速开始（用 TCMAI 自带的 venv）

### 三步页（本机图形界面，v0）——不想敲命令就用它

双击 `start_ui.bat`（等价于 `D:\TCMAI\venv\Scripts\python.exe ui.py`）→ 浏览器自动打开
`http://127.0.0.1:8765/`：**选药材 → 条件/轮数 → 开始预测**（真跑引擎，约几秒~几分钟）→
结果区给「一页报告 / 台账 CSV / 索引 TSV」链接 + 运行记录（成分取舍 / 开关 / 对子）。
公开版只显示「单味 / 物种」「方剂」「历史」「设置」四个工作区，不提供任意目标逆合成。
逆合成只保留在内部研究命令行，需显式设置 `CHRISTOS_RESEARCH_MODE=1`；公开版不把
目标 → 路线 → 条件/采购链暴露给普通用户。
只绑本机 127.0.0.1、只写 `out\`，与命令行完全同一条路。停：控制台 Ctrl+C。

```powershell
cd D:\TCMAI\chemreact

# ① 环境自检（引擎目录、模板数、黑名单数、数据库只读连通）
D:\TCMAI\venv\Scripts\python.exe chemreact.py info

# ② 正向：甘草成分 1 轮 -> 候选产物台账（CSV + TSV + 一页 HTML 报告，写在 out\）
D:\TCMAI\venv\Scripts\python.exe chemreact.py predict --herb 甘草 --limit 12 --rounds 1

# ③ 内部研究专用：给目标分子找路线（公开版默认关闭；需显式设置研究模式）
$env:CHRISTOS_RESEARCH_MODE='1'
D:\TCMAI\venv\Scripts\python.exe chemreact.py routes --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2

# ④ 受限池问答：只用你这批底物能不能做出目标
D:\TCMAI\venv\Scripts\python.exe chemreact.py routes --target "CC(=O)Oc1ccccc1C(=O)O" `
    --pool-file D:\ProgramData\DSHNS\chemreact-staging\reports\_pool_aspirin_demo.txt --depth 1
```

> **逆模板库版本（2026-10-15 起）**：生产默认 = **v2·freq≥10**（18,914 条；加载约 1 秒 /
> 600 MB；5,002 目标实测 any-hit 91.9%）。回退或切换：设环境变量 `CHEMCREACT_RETRO_LIB`
> 指向任一 jsonl（旧库在 `reports\retro_templates_clustered.jsonl`）。

## 输出

* `out\<时间戳>_<药材|smiles>.csv`：**产物台账**（一行一条出处路径；含方向标注、条件依据、
  模板 support、元素收支等列——"只打标记、不删产物、不排序"）
* `out\<时间戳>_<药材|smiles>.tsv`：**产物索引**（SMILES / InChIKey / 出处数）
* `out\<时间戳>_routes.txt`：逆合成路线报告（含每一步"在池内/不在池内 + 可用性原因"）
* `out\<时间戳>_routes.report.html`：路线**一页报告**（目标结构图 + 每条路线的步骤表：
  反应/目标/前体（在池/不在池着色）、可用/不可用标注；单文件、离线可开）
* `out\<时间戳>_<药材|smiles>.report.html`：**一页式报告**（产物去重表 + 出处明细 +
  **分子结构图** + **运行记录**；带方向筛选 / 关键词过滤 / 「只看有条件证据」开关，
  **只影响浏览显示、不改数据不排序**；结构图最多画前 120 个；单文件、离线可开）
* `out\<时间戳>_<药材|smiles>.meta.json`：**运行留证**——成分取舍（取谁 / 可用多少 /
  谁没参与）、开关状态（switches）、对子覆盖（pair_coverage：预算、伙伴数范围、是否截断）

## 常用开关

| 开关 | 说明 |
|---|---|
| `--rounds N` | 枚举轮数（★由你掌握★；也是唯一"收敛控制"） |
| `--limit all` | 该味药**全部成分**都不截取（默认 12；会提示对子预算与所需 `--max-pairs`） |
| `--fair-pairs` | 对子超预算时的公平截断：每个成分摊到大致相同的伙伴数（默认关 = 旧行为） |
| `--chp-priority` | **药典判据优先**：Tier-0（药典含量测定成分）排前、同层按限量值降序（默认关） |
| `--cond 煎煮` | 条件档案名（温度/溶剂窗口与试剂门控用它） |
| `--reagents "NaBH4,..."` | **内部研究专用**；公开版关闭，需 `CHRISTOS_RESEARCH_MODE=1` |
| `--triples` | 三组分模板（默认关：慢 ~40×，当前 demo 增益有限） |
| `--retro-blacklist` | 逆模板黑名单（默认关：51 条 never-usable + 29 条 R2 家族 + 3 条 no-op = 83 条；打开后 3,025 → 2,942） |
| `--usable-only` | 路线只显示判为"化学可用"的（仍不排序） |
| `--no-report` | 不生成一页 HTML 报告（默认生成；报告生成器在引擎 `tools\make_report.py`，单一来源不复制） |

## 环境变量

* `CHEMCREACT_STAGE`：覆盖引擎目录（默认 `D:\ProgramData\DSHNS\chemreact-staging`）。
  如果哪天 chemreact-staging 挪了位置，设这个变量即可，不用改代码。

## 安全边界（每次跑都会遵守）

1. 数据库**只读**（`file:...?mode=ro`；沙箱/无 -shm 环境自动回退 `immutable=1`，仍是纯只读）。
2. 不写 `formula_db*` / 不删 `-wal/-shm` / 不动 VS Code 与爬虫相关的任何文件。
3. 输出只落在本目录 `out\`（可用 `--out` 改）。
4. **公开版安全模式**：任意目标逆合成、自由辅助试剂和可购砌块查询默认关闭；
   普通用户不需要也不应该修改数据库。
5. **边车文件说明（实测，2026-10-14）**：在有写权限的环境里，第一次以只读模式打开
   WAL 模式的 `tcm.db`，SQLite 会生成 `tcm.db-wal`（0 字节）与 `tcm.db-shm`（32 KB）。
   这是 WAL 的正常机制，**没有写入任何数据**（主库时间戳不变、wal 为空）；
   按项目纪律这两个文件**一律不删**（爬虫/今后的写入会正常复用）。
   若想要"零边车"读取（`immutable=1`），代价是爬虫写入期间可能读到旧快照——默认不用。

## 已知边界（老实说）

* 查不到 ≠ 不存在：只等于"当前模板库 + 当前轮数没枚举出来"。
* 条件层只打标记（分布外会标出来），不替你筛产品；三组分模板默认关。
* 逆合成的"可用性"是启发式判据（残基/放大/惰性/荒谬四类），会标注原因供人工判断；
  判据在中等分子上有已知的不稳定性，报告里会一并说明。
