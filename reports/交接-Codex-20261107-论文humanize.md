# 交接给 Codex：论文剩余 humanize + 收尾

> 写于 2026-11-07 15:55（Asia/Shanghai）。交接原因：本文会话无法调用 `humanize_study`（工具只对**新起的 agent 实例**可见），
> 派子代理去调时 6 个里有 3 个在写文件前被运行时掐死、重试同样死法。用户决定把剩下的写作交给有原生 humanizer 的 Codex。

---

## 0. 一句话

**论文主体已经定稿并改过 8 轮事实/数字错误；只剩三批段落没跑第 3 遍 humanize（英文案例节、中文结果节、中文案例节）。**
输入 JSON 已经切好放在 `_diag/`，跑完按规则应用即可，**不需要再判断任何数字或事实**。

---

## 1. 论文文件在哪

| 角色 | 路径 |
|---|---|
| 英文稿（权威） | `chemreact-staging/reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.md` |
| 中文稿 | `chemreact-staging/reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.md` |
| 英文 HTML（由脚本生成，勿手改） | 同目录 `manuscript-peerj-humanizer-20261030.html` |
| 中文 HTML | 同目录 `manuscript-peerj-humanizer-20261030-zh.html` |
| HTML 构建脚本 | `tools/_build_peerj_humanizer.py`、`tools/_build_peerj_humanizer_zh.py` |
| 数字口径总账 | `reports/paper/基准口径-2026-11-04.md` |
| 一致性审计工具 | `tools/audit_paper_consistency.py`（只读，输出到 stdout） |

重建 HTML（改完 md 必须跑）：

```powershell
$PY = 'D:/TCMAI/venv/Scripts/python.exe'
& $PY -I tools/_build_peerj_humanizer.py
& $PY -I tools/_build_peerj_humanizer_zh.py
& $PY -I tools/audit_paper_consistency.py
```

审计输出的 `MULTIPLE VALUES` 大多**不是错误**——那是同一指标在不同实验里的不同值（见 §4）。真矛盾的判据只有一条：
**同一实验、同一口径下出现两个不同数字**。

---

## 2. 剩下要做的三批（这是唯一剩下的写作任务）

三个输入文件已切好，每批 6~8 段。**`sections` 必须传字符串数组**，每项格式 `"<id>::<正文>"`（工具按第一个 `::` 拆 id）：

| 批次 | 输入文件 | 段数 | 目标稿件 |
|---|---|---|---|
| EN case | `_diag/hz_en_case2.json` | 6 | 英文稿 |
| ZH results | `_diag/hz_zh_results2.json` | 8 | 中文稿 |
| ZH case | `_diag/hz_zh_case2.json` | 6 | 中文稿 |

调用参数：`genre="article"`, `mode="polishing"`, `language` 与批次一致（`en` / `zh`）。

**已经跑完的（不要重跑）**：
- 英文方法 8 段、英文结果 8 段 → 已应用，提交 `2ab61fe`
- 中文方法 7 段（第 8 段 `before==after`，跳过）→ 已应用

**应用规则**（脚本 `_diag/apply_hz_batch.py` 已经实现，可直接用）：

```powershell
& $PY -I '_diag/apply_hz_batch.py' en 'hz_en_case2.out.json'
& $PY -I '_diag/apply_hz_batch.py' zh 'hz_zh_results2.out.json'
& $PY -I '_diag/apply_hz_batch.py' zh 'hz_zh_case2.out.json'
```

脚本只接受同时满足两条的条目，其余打印 SKIP 并跳过：

1. `status == "ok"`（`needs_revision` / `skip` 一律不动）
2. `before` 在稿件里**恰好出现一次**（0 次说明段落对不上，>1 次说明会误伤，都不改）

跑完一批就重建 HTML 并 `git commit`，不要攒到最后。

---

## 3. 铁规矩（违反任何一条都得回滚）

1. **数字一个不能改**。humanize 的 `checks.numbers_preserved` 必须为 `true`。若工具建议改数字，**拒绝**。
2. **表格结构、图、图注不动**（`forbidden` 列表里明确写了）。
3. **受保护术语原样保留**：`RDF`、`candidate-set recall`、`top-1`、`ORD`、`USPTO-50k`、`TCM`、`DBE` 等。
4. **DOI 与参考文献编号不动**。
5. 改写长度比 ≤1.1（工具自己会报 `max_length_ratio`）。
6. 只做「没写到位」的润色（断了 / 硬了 / 凉了 / 空了 / 说多了），**不要顺手改风格**。

---

## 4. 已经核对过的事实（不要再改，也不需要重新验证）

### 4.1 「五个案例」不是错的

中文方法节「文献一致性验证」写「固定了五个案例」，正文只列四项：
甘草酸→甘草次酸、Rb1→Rg3、乌头碱两步酯水解、芦丁→槲皮素。

**这是五项**——乌头碱那项占两条（乌头碱→苯甲酰乌头原碱；苯甲酰乌头原碱→乌头原碱）。
依据：`reports/literature_paths_20261104.json` 里 `cases` 长度 = 5，五条状态全部 `consistent`。
humanize 工具曾把它标成 `needs_human`，**是误报**。

### 4.2 参考文献 26 条：0 条需要修改

`tools/audit_references.py`（只读，输出 `reports/reference_audit_20261107.json`）机器核对结果：

- `ok 19` / 无 DOI 6 / Crossref 不收录 1
- **0 处年份错、0 个死 DOI、0 条未被引用**

两条「不完全可核」的已确认无误，不要动：

- `[24]` Kim & Lim 2017（`10.3746/pnf.2017.22.2.131`）：韩国刊，Crossref 不收录该刊，但 doi.org → `koreascience.or.kr`（E1FSA3 / v22n2 / p131 / 2017），文章真实存在。
- `[13]` Tox21 10K（`10.1021/acs.chemrestox.0c00264`）：写 2021 是对的，`published-print` = 2021-02-15，Chem Res Toxicol 34(2):189–216。

### 4.3 已修正过的 8 处事实/数字错误（防止有人「改回去」）

| 提交 | 修正内容 |
|---|---|
| `dc1917a` | 逐类召回表 10 行**整表替换**（原表按 n 加权是 55.4%/82.3%，属「立体关」那一对，与头条 58.73%/91.69% 不同源）；结论句改为 Class 5 +78.0、Class 9 +61.7、Class 6 +53.8、Class 8 +47.3 |
| `aa74290` | 58.73 与 55.53 的差异机制改为「双组分 mined 模板被 cap 8 截断」 |
| `811e786` | 补一句「无法二分定位：冻结那次早于第一个提交」 |
| `86f15e1` | 数据层计数：12,071 → **6,743**；「3,228 production templates」错认 → 拆成 Forward 9,770+41,619 / Retro 3,228 clustered（3,025 compiled）；删掉无出处的 9,177 |
| `f2cf14d` | 摘要加「candidate-set recall」限定 + 外部切分（官方 5,001 / MIT 39,176）写进 Results |
| `1ce646b` | fig5 去掉混量纲的第 6 根柱（493/500 是产物匹配比例，不是召回） |
| `1c02871` | extent 三处措辞统一为「只标注、不筛选」 |
| `bf3646c` | 摘要数据层句与 provenance 段 humanize |

---

## 5. 论文现在的数字（改稿时对照，不要改）

| 指标 | 值 | 口径 |
|---|---|---|
| 正向召回（默认档） | **92.01%**（46,020/50,016） | USPTO-50k 全集，煎煮，立体开 |
| 正向召回（官方切分） | **91.71%**，top-1 **43.28%**，MRR 0.5496，候选 21.8 | 4,993 可评 / 5,001 |
| 正向召回（USPTO-MIT） | **71.18%**，top-1 **32.81%**，候选 20.1 | 39,176 确定性抽样 / 479,035 |
| 基线（冻结） | **58.73%**；当前代码同配置 **55.53%** | cap 8，无模板池 |
| 逆向 any-hit | **94.74%**（4,739/5,002） | × `lib_uspto50k_excl_v2.jsonl`，stride 10 |
| 逆向 any-hit | **79.81%**（39,919/50,016） | × `lib_uspto50k_excl.jsonl`，stride 1 |
| 多步逆向 | **47.67%**（143/300）≤2 步 / **72.33%**（217/300）≤3 步 | `_freq10` 库，16,891 模板，beam 4 |
| 模板泄漏 | **0 / 50,016**、**0 / 479,035** | 严格同反应 |
| 模板最近邻相似度 | 中位 **0.2308** | 每反应物都能找到 ≥0.85 相似者：0/3,000 |
| 文献回溯 | **5/5** | `reports/literature_paths_20261104.json` |
| 炮制 | **3 consistent + 3 formula_only** | `reports/paozhi_paths_20261104.json` |
| 方剂（四逆汤／黄芩汤／桂枝汤／麻黄汤／小柴胡汤） | 4/4、1/1、3 项一致、1 项、3 项 | `reports/formula_*.json` |
| 整味药（前体纳入后） | **3/3 consistent** | `reports/whole_herb_20261106*.json` |

条件层是**标注层，不筛选产物**——不要写成「条件会过滤候选」。
诱饵对特异性 ≈ 0（100% vs 99.8%）已写进 Limitations 口径，不要淡化。

---

## 6. 仓库与发布状态

- 主仓：`D:\ProgramData\DSHNS\chemreact-staging`，HEAD 见 `git log`（最新提交含 `2ab61fe`）。
- 发布快照仓：`D:\ProgramData\DSHNS\_github_chemreact`（1,226 文件，工作树 82.7 MB）。
- 远端：`https://github.com/VegFisx/Christos`，`main` = **`2389b03`**（1,265 文件 / 82.6 MB，含 `data/tcm_subset.db` 2,052,096 B）。
- **待办**：`2ab61fe` 之后的稿件改动尚未推远端；推法与之前一致——复制改动文件进快照仓 → `git add -A -- reports` →
  `git write-tree` → `git commit-tree <tree> -p origin/main -m "..."` → `git update-ref refs/heads/sync5 <sha>` → `git push origin sync5:main`
  （`origin/main` 与快照 HEAD 无共同祖先，**不能普通 push**）。
- 用户网页侧待办：删掉测试分支 `auth-probe`（`git push --delete` 被安全网拦）。

---

## 7. 环境（这台机器上跑任何东西之前先看这条）

```powershell
$PY = 'D:/TCMAI/venv/Scripts/python.exe'   # 用这个，不要用 D:\TCMAI\.venv
& $PY -I <脚本>                             # 必须 -I
```

- Python 3.12.10 / rdkit 2026.03.6；`D:\TCMAI\venv` 的 `pyvenv.cfg` 曾在 11-04 被写成一段终端转写文本，已修好。
- git 不在系统 PATH：`D:\ProgramData\DSHNS\tools\git\cmd\git.exe`（或 `tools\git.cmd`）。
- 改文件**不要用** PowerShell 的 `Set-Content` / here-string 塞代码：会写 BOM、写坏中文（`U+E634`、`U+FEFF`）、丢引号。
  要么用编辑工具，要么把脚本写成 `_diag/*.py` 再执行。
- 大任务别用 3 个以上 worker：这台机 15.7 GB 内存，宽档每 worker 2.4 GB。

---

## 8. humanize 工具本身的调用要点（供 Codex 对照）

- `sections` 是**字符串数组**：`["system-overview::…", "data-sources::…"]`。
- 返回值字段序：`genre, mode, language, needs_human, needs_human_reason, structure, samples,
  targets[{index,section,language,status,risk,before,after,why}], forbidden, checks, meta`。
- `checks` 里必看：`all_before_found`、`numbers_preserved`、`no_banned_phrases`、`max_length_ratio`。
- 只有 `status == "ok"` 的条目可以应用。

---

## 9. 交完这一棒就结束的部分

以下都已定稿，不需要再动：四个基准族（正向/逆向/多步/泄漏）、三套 TCM 验证、条件层的「标注」定位、
摘要与 Results 的外部切分段、fig5、参考文献、`REPRODUCE.md` 与 `data/tcm_subset.db`。
