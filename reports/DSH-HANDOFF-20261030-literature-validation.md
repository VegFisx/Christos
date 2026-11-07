# DSH 交接：Christos 文献一致性验证

日期：2026-10-30  
工作区：`D:\ProgramData\DSHNS`  
当前任务：根据导师意见，在论文中加入“已发表实验与模型结果对照”的验证

## 1. 先看什么

按顺序阅读：

1. `D:\ProgramData\DSHNS\AGENTS.md`
2. 本交接单
3. `reports/paper/literature_validation_20261030.md`
4. `reports/paper/literature_validation_20261030.json`

核心口径：这是**回溯性文献一致性验证**，不是湿实验验证。

## 2. 已完成的验证

验证脚本：

`tools/validate_literature_conversions.py`

运行：

```powershell
python tools\validate_literature_conversions.py
```

脚本会自动：

- 以只读方式从 `D:\TCMAI\tcm.db` 读取底物、目标产物和文献中间体；
- 用当前 staging 引擎重新运行 5 个案例；
- 记录命中规则、轮次、候选数、分子式差和文献中间体；
- 对本地库已有的中间体再运行一轮，检查能否继续生成目标；
- 用 PubChem 标准立体结构做独立重跑；
- 输出 JSON、CSV 和 Markdown。

当前结果：

| 指标 | 结果 |
|---|---:|
| 产物连接层命中 | 5/5 |
| 使用文献预期水解规则 | 5/5 |
| PubChem 立体结构重跑完整命中 | 1/5 |
| PubChem 连接层命中 | 5/5 |
| 文献记录 | 8 篇 |

五个案例：

| 案例 | 规则 | 候选数 | 结论 |
|---|---|---:|---|
| 甘草酸 → 甘草次酸 | `hydrolysis_glycoside_001` | 63 | 产物和反应族一致；文献中间体不在本地库，详细顺序未定 |
| 人参皂苷 Rb1 → Rg3 | `hydrolysis_glycoside_001` | 102 | `Rb1 → Rd → Rg3` 可通过两次单轮运行复现；引擎也允许 Rb1 直接到 Rg3 |
| 乌头碱 → 苯甲酰乌头原碱 | `hydrolysis_ester_001` | 24 | 丢失 C2H2O，与 C8 乙酰酯水解一致；仅能确认到连接层 |
| 苯甲酰乌头原碱 → 乌头原碱 | `hydrolysis_ester_001` | 27 | 丢失 C7H4O，与 C14 苯甲酰酯水解一致；仅能确认到连接层 |
| 芦丁 → 槲皮素 | `hydrolysis_glycoside_001` | 61 | 异槲皮素出现且可继续生成槲皮素；PubChem 立体结构重跑完整命中 |

重要限制：

- 本地 `tcm.db` 的复杂天然产物大多是二维、无立体层 SMILES。
- 因此四个案例只能确认 `constitutional/connectivity match`，不能宣称完整立体异构体验证。
- 只有槲皮素案例在 PubChem 立体结构重跑中获得 exact stereo hit。
- 当前运行条件为水、100°C、60 分钟、pH 6.5、空气；文献条件分别是亚临界水、蒸制、酶转化、酸水解或长时间水解，不能把结果写成“复现实验条件”。

## 3. 论文已改到哪里

中英文 Markdown 与 HTML 已加入：

- `Materials and Methods → Literature consistency validation`
- `Results → Literature consistency results`
- 5 个案例的产物/规则/路径对照表
- 立体化学与条件不可比性的限制
- 数据可用性说明
- 参考文献 19–26

文件：

- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.md`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.html`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.md`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.html`

**PDF 暂未更新。** 用户明确说先不要生成 PDF，后续可能还有修改。不要拿 17:54 生成的旧 PDF 当作当前版本。

通讯作者仍为：

- 英文：`[To be completed]`
- 中文：`[待填写]`

当前两版均有 26 条编号连续的参考文献。

## 4. 证据文件

验证结果：

- `reports/paper/literature_validation_20261030.json`
- `reports/paper/literature_validation_20261030.csv`
- `reports/paper/literature_validation_20261030.md`
- `reports/paper/literature_validation_pubmed_20261030.xml`
- `reports/paper/pubchem_literature_validation_20261030.json`

文献核验：

- `reports/paper/reference_verification_20261030/manifest.json`
- `reports/paper/reference_verification_20261030/README.md`
- `reports/paper/literature_validation_fulltext_20261030/`

其中五个开放全文来自 Europe PMC：

- Piao 2020：PMC7582514
- Ryu 2017：PMC5628343
- Li 2016：PMC5051147
- Kim 2017：PMC5503422
- Yang 2019：PMC6779085

Crossref 没收录两篇 *Preventive Nutrition and Food Science* DOI；
它们以 PubMed 元数据为准，不能写成“Crossref verified”。

## 5. 下一步必须处理

### P0：先判断论文如何表述“验证”

建议使用三层表述：

1. 产物连接层：5/5
2. 反应族与断裂键类型：5/5
3. 完整立体结构与逐步路径：未全部成立

禁止写成：

- “五条实验全部复现”
- “五条都得到立体结构验证”
- “模型与文献条件一致”

### P0：决定是否补立体结构

两条路线：

1. 保守路线：论文明确限定为 `connectivity-level literature consistency`，保留当前 1/5 exact stereo 结果。
2. 加强路线：用 PubChem/ChEBI 等标准立体结构建立独立参考集，重新验证并调查为什么目前只有槲皮素案例完整命中。

若要增强，不要手写结构；所有 SMILES/InChIKey 从本地库或官方数据库脚本获取，并记录 CID、来源和版本。

### P0：处理详细路径差异

- `Rb1 → Rd → Rg3` 已可走通，但 `Rb1 → Rg3` 直连也出现。论文需明确这是额外捷径，不能声称只走文献路径。
- 甘草酸案例缺少单葡萄糖醛酸中间体，详细先后顺序仍是 unresolved。
- 乌头碱的 C8/C14 位点目前由分子式差和文献结构推断，尚未通过原子映射直接确认。

### P1：补强证据

- 为每个案例增加独立论文或原文证据段落引用，不能只靠摘要。
- 考虑把中间体加入独立的验证补丁表，而不是直接改 `tcm.db`。
- 增加阳性和阴性对照：
  - 阳性：文献明确报告的产物；
  - 阴性：同底物下文献未报告的反应族或产物。
- 明确候选数、命中轮次和不排序的限制。

### P1：最终成稿

用户确认所有修改后：

1. 再统一生成中英文 PDF；
2. 检查 PDF 中的表格、图 5 caption 和参考文献；
3. 更新 `reports/SESSION-HANDOFF-20261029.md` 或另建最新交接；
4. 检查 `arxiv-submission.md` 的参考文献数量。

## 6. 运行与边界

- 当前普通 `python` 环境有 RDKit 2026.09.1，验证脚本已实际跑通。
- 用户说暂不生成 PDF。除非用户明确解除，不要调用 Edge 打印 PDF。
- `D:\TCMAI` 只读。不要修改 `tcm.db`、`formula_db.json`、任何 `-wal`/`-shm`。
- 当前 Web 服务不是本轮重点；不要重启或覆盖 `D:\TCMAI\chemreact`，除非用户明确要求。
- 网络查询优先使用已保存的 PubMed/Europe PMC/PubChem 快照；新增联网来源前仍按 AGENTS.md 先确认网络条件。

## 7. 建议 DSH 的第一条动作

先读：

```text
reports/paper/literature_validation_20261030.md
reports/paper/literature_validation_20261030.json
```

然后只做一件事：检查中英文稿件中的验证章节是否忠实反映这组结果。确认后再决定是否补立体结构和重跑路径。
