# 交接给 Claude Code（2026-11-04）

工作区：`D:\ProgramData\DSHNS`，主项目 `chemreact-staging`。用户原话：「行啦行啦，给claudecode做吧」——由 Claude Code 接手继续。

## 1. 先读这三份

1. `D:\ProgramData\DSHNS\AGENTS.md`（工作规矩，尤其 §〇 项目范围铁律、§一 查数据先写脚本、§六 省钱执行模式 + §11.8 已放弃的方向）
2. `chemreact-staging\reports\接手报告-2026-11-04.md`（环境与全貌）
3. `chemreact-staging\reports\第一百轮-放宽装载取舍-20261104.md`（当前正在做的事）

## 2. 环境（都已修好，别重装）

| 用途 | 怎么用 |
|---|---|
| Python | `D:\TCMAI\venv\Scripts\python.exe`（3.12.10，rdkit 2026.03.6）——`pyvenv.cfg` 被人写坏过，已修 |
| 快速跑 | `D:\ProgramData\DSHNS\tools\py.cmd <脚本>` |
| git | `D:\ProgramData\DSHNS\tools\git.cmd`（MinGit 2.56.0.4，无管理员权限）；新开终端后 `git` 直接可用 |
| node | `C:\Program Files\nodejs\node.exe`（`tools\check_ui_js.py`、报告 JS 检查用） |
| tcm.db | **只读**：`sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)`，别删 `-wal/-shm` |

`git log` 顶部：`541acb7` ← `898f490` ← `45e63b7`；工作树干净。

## 3. 已完成（第 84~100 轮，皆有报告 + 提交）

- **84** extent 层（条件→反应进程）
- **85** 温度语义统一（窗口之上不罚）
- **86** 一页报告里的「反应路径」视图（`core/reaction_paths.py`、`tools/dump_paths.py`）
- **87** 文献对照 5/5（产物 + 路径）
- **88** 炮制 6 案例：3 条完整一致、3 条只到分子式级
- **89** 立体化学：默认改为开、台账记模板 SMARTS、报告显示逐跳立体结论
- **90** 基准口径钉死（92.01% / 82.77% / 91.69% / 82.32% 四个数字的归属）+ 原子守恒观测量
- **91** 炮制缺口定性（`also_rules` 修归因）+ `validate_paozhi_paths.py`
- **92~93** 方剂煎煮：四逆汤 4/4、黄芩汤 1/1、甘草酸补 2 轮
- **94** 泄漏检查 0/50,016 + 排序指标（top-1 42.67%）
- **96** 排序改用「发射序」（top-1 42.67%，此前 scorer 0.3250）
- **97** extent/curated 先验全部无效；诱饵对假阳性 99.8%（用户已明确：不再攻反应可行性）
- **98~99** 缺产物归因：226/3,000 miss；模板存在但装载截断 95 条（42%）
- **100** 放宽装载取舍：召回 92.47→95.27%，但 top-5 掉 10.7 pp、耗时 3.7 倍 → 默认不改

## 4. 当时正在做的（用户喊停）

全量 50,016 条 × 放宽档基准（约 1.5~2 小时），已 kill，未产出。要重跑：

```powershell
$env:CHEMCREACT_BENCH_EXTRA_MIN_SUPPORT='1'
$env:CHEMCREACT_BENCH_EXTRA_LIMIT='60000'
$env:CHEMCREACT_BENCH_MONO_LIMIT='60000'
$env:CHEMCREACT_BENCH_MONO_CO_REAGENT='1'
$env:CHEMCREACT_BENCH_MAXPROD='128'
$env:CHEMCREACT_BENCH_OUT='D:/ProgramData/DSHNS/chemreact-staging/reports/paper/results/wide128_20261104'
$env:CHEMCREACT_BENCH_TAG='wide128'
D:\TCMAI\venv\Scripts\python.exe -I tools\paper_bench_50k_forward.py 100000 3
```

已有基线：立体开 **92.01%（46,020/50,016）**、1,792 s；`CHEMCREACT_STEREO_CANON=0` → **82.77%**、1,737 s。

## 5. 别再做的事（用户已明确否掉）

1. **反应可行性 / 特异性**（AGENTS §11.8）：「只要文献标出的产物都有就行」。
2. **extent 进排序**：实测更差（0.4271 → 0.3357）。
3. **仓库瘦身 / 基准提速**：`User said (m02168): "20不要做，时间长很正常"`。
4. 改论文正文：必须走 humanizer（AGENTS §十），只动数字。

## 6. 容易踩的坑

- `core/smartreact_engine.py` 是 **CRLF**；批量改要先 `Replace("\r\n","\n")`，写回前还原。
- 改代码用 edit 工具，不要用 PowerShell `Set-Content`（BOM）或字符串 `.Replace` 拼 Python（引号配对会崩）。
- `$PY/$py` 在 PowerShell 里是同一个变量（大小写不敏感），会覆盖解释器路径。
- 后台跑长任务：`run_in_background`，不要在一个回合里干等（AGENTS §6.5）。
- 证伪一条路要留数字：本仓库所有结论都要求「实测」标注，不要写「推断」当结论。
