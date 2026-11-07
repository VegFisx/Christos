# 炮制 A/B/C 执行总结（2026-10-31）

结论：A 完成；B 完成（大黄只做部分映射）；C 完成（P2 原型，边界见 §4）；audit ERROR 0。
严格模式已设为炮制档默认（§8，2026-10-31 追加）。
烟雾测试一律 `--herb 甘草 --limit 6 --rounds 1`。

## 1. 改了哪些文件

### 修改
| 文件 | 内容 |
|---|---|
| `conditions/templates.py` | 新增「炮制·盐炙」「炮制·姜炙」两个条件档 |
| `core/smartreact_engine.py` | 新增 `use_base_templates` 开关（默认 True）；炮制严格模式传 False，基础模板库不参与枚举 |
| `core/query_base.py` | `RunSpec.use_base_templates`（默认 True）与引擎透传；`engine_notes` 增加 `base:` 一行 |
| `integration/tcmai_bridge/chemreact.py` | COND_EN；炮制辅料加载与 seeds 追加；盐炙/姜炙/辅料备注；processing 计数；`--no-paozhi-adjuvant`；炮制严格模式（默认）与 `--paozhi-base-templates` |
| `integration/tcmai_bridge/ui_page.html` | 三个下拉框、两处预设表、COND_EN/EN、中文提示（已写明基础模板默认关闭）、结果页辅料行 |
| `rules/paozhi_evidence.json` | 糖苷水解 5 源、酯水解 1 源、脱水 2 源、美拉德 2 源 |
| `reports/paper/paozhi_sources_20261031.json` | 新增 3 条盐炙/姜炙条件；何首乌改映射、新增大黄 |
| `reports/paper/paozhi_sources_20261031.md` | 同上表格；更新过期结论，补第三轮 A/B/C 小节 |

### 新增
`conditions/paozhi_adjuvants.py`；`rules/paozhi_adjuvants.json`；
`tools/build_paozhi_adjuvants.py`、`probe_paozhi_adjuvants.py`、`probe_paozhi_adjuvants2.py`、
`fetch_paozhi_fulltexts.py`、`fetch_paozhi_html.py`、`fetch_cn_dosage.py`、`check_ui_js.py`、`run_paozhi_smoke.py`；
`reports/_paozhi_src/`（PMC11335691.xml、PMC6121093_frontiers.html、cn/*.html 5 个）；
`reports/_paozhi_smoke/third_*`（每次运行的 csv/tsv/meta）。

### 未动
`D:/TCMAI` 只读：tcm.db 经 `file:...?mode=ro` 访问，未写库、未删 `-wal`/`-shm`；
tcm.db 的 mtime 仍是 2026-10-17。未生成 PDF，未改论文稿。

## 2. A：盐炙 / 姜炙 —— 完成

### 数值与出处
| 方法 | 数值 | 出处 | 备注 |
|---|---|---|---|
| 盐炙（通则） | 食盐 2 kg / 100 kg，文火 | 中国药典 2020 通则 0213（转引医学教育网 `https://www.med66.com/zhongyaoxue/ziliao/wx2002058108.shtml`） | 「盐炙时，每100kg药物，用食盐2kg。」 |
| 盐炙（杜仲） | 2% 盐水；150°C；10 min | 药物分析杂志 2009, 29(11):1817–1820 | 「每1 kg杜仲药材喷洒2%盐水溶液拌匀润透，150 ℃炒制10 min。」（摘要级） |
| 盐炙（沙苑子） | 2% 食盐水 4 mL/30 g；100°C；15 min；闷润 8 h | 中草药 2025, 56(9):3121–3130, doi:10.7501/j.issn.0253-2670.2025.09.010 | 备选档 |
| 姜炙（通则） | 生姜 10 kg / 100 kg（干姜 1/3），文火 | 同上药典通则｜「姜炙时，每100kg药物，用生姜10kg。」 | |
| 姜炙（黄连） | 15% 姜汁；150°C；40 min | 中国药师 2016（万方） | 「生黄连加15%姜汁润透后，在150℃下烘制40 min…」 |
| 姜炙（厚朴/栀子） | 10% 姜汁；170°C/6 min；4.5 min | 中国中医药资讯 2010 等 | 只记备注，未进档 |

### 条件档取值
- 炮制·盐炙：`solvent=water, 150°C, 10 min, pH 7, air`（杜仲温度/时间 + 药典 2% 盐）。
- 炮制·姜炙：`solvent=water, 150°C, 40 min, pH 7, air`（药典 10% 生姜 + 黄连温度/时间）。
- 同步了 cond / f_cond / set_cond 三个下拉框、两处预设表、COND_EN/EN、中文提示；
  chemreact.py 备注写明「NaCl 为离子，未作为共底物」「姜汁多成分未逐个加入」。

### 烟雾测试（甘草 limit 6，1 轮）
| 条件 | 产物（严格模式前） | 引擎秒 | 墙钟秒 |
|---|---|---|---|
| 炮制·盐炙 | 225 | 1.71 | 2.15 |
| 炮制·姜炙 | 225 | 1.71 | 2.15 |

两档均 0 个共底物（按设计：盐/姜汁不入 seeds）。

## 3. B：何首乌 / 大黄 —— 完成（大黄部分映射）

| 药材 | 可映射的文献观察 | 规则 | 出处 / 引句 |
|---|---|---|---|
| 何首乌（九蒸九晒） | THSG 水解；脱水、异构化、美拉德参与；5-HMF 为美拉德标志物 | hydrolysis_glycoside_001、elimination_dehydration_001、maillard_simplified_001 | Front Pharmacol 2018, doi:10.3389/fphar.2018.00934（PMC6121093）｜「both cis-THSG and trans-THSG are readily hydrolyzed…」「Several mechanisms, namely hydrolysis, dehydration, isomerization, and Maillard reaction appear to be involved…」 |
| 大黄（酒炙/酒蒸/炒炭） | 糖苷水解；结合蒽醌↓、游离蒽醌↑ | hydrolysis_glycoside_001 | Front Pharmacol 2024, doi:10.3389/fphar.2024.1442297（PMC11335691）｜「the processing of rhubarb involves not only the hydrolysis of glycosides but also complex chemical changes.」 |

何首乌原文的「异构化」无对应炮制证据规则 → 记为「**不可映射**」（原因：无该反应类证据），未硬加。
大黄原文另列 carbonization / oxidation / decomposition / condensation，**现有规则库没有对应的炮制证据规则，记为「不可映射」，未硬加**。
证据表计数：糖苷水解 5、酯水解 1、脱水 2、美拉德 2（meta 的 `n_sources` 已同步）。

## 4. C：辅料共底物（P2 原型）—— 完成（原型）

### 结构来源（全部只读取自 tcm.db，未手写 SMILES）
| 档 | 辅料（药材行） | 共底物 | ingredient_id |
|---|---|---|---|
| 炮制·蜜炙 | 蜂蜜 HERB001711 | 葡萄糖 C6H12O6；果糖 C6H12O6 | HBIN028037；HBIN026793 |
| 炮制·酒炙 | 黄酒 HERB002538 | 乙醇 CCO | HBIN015097 |
| 炮制·醋炙 | 醋 HERB000960 | 乙酸 CC(=O)O | HBIN014399 |

生成脚本 `tools/build_paozhi_adjuvants.py` → `rules/paozhi_adjuvants.json`。
- 只在 `炮制·*` 档启用；非炮制条件永不加载（守卫运行 0 共底物）。
- 开关：默认开；`--no-paozhi-adjuvant` 或 `CHEMCREACT_PAOZHI_ADJUVANT=0` 关闭（两者均实测）。
- meta 的 `switches.paozhi_adjuvant` 记录开关，`processing` 记录
  `adjuvant_enabled / n_co_substrates / co_substrates / n_products_from_adjuvant`；
  CSV 里辅料产物 `source_herb=辅料:<名>`，与药材产物分开。

### 烟雾测试（甘草 limit 6，1 轮）
| 运行 | 产物（严格模式前） | 共底物 | 以辅料为底物的产物 | 引擎秒 | 墙钟秒 |
|---|---|---|---|---|---|
| 蜜炙（加载辅料） | 298 | 葡萄糖+果糖 | 3 | 2.00 | 2.47 |
| 蜜炙（`--no-paozhi-adjuvant`） | 225 | 0 | 0 | 1.80 | 2.24 |
| 醋炙（加载辅料） | 367 | 乙酸 | 38 | 2.36 | 2.80 |
| 醋炙（`--no-paozhi-adjuvant`） | 329 | 0 | 0 | 2.58 | 3.02 |
| 醋炙（`CHEMCREACT_PAOZHI_ADJUVANT=0`） | 329 | 0 | 0 | 2.58 | 3.02 |
| 守卫：煎煮（非炮制） | 705 | 0 | 0 | 40.10 | 40.78 |

以上为严格模式前的历史数据；严格模式后的对比见 §8。

辅助说明：辅料作为「第二个底物」参与时，产物记在药材名下，`n_products_from_adjuvant` 只数辅料作底物的产物；
所以蜜炙总产物 +73、其中标记辅料的只有 3 个（+70 属于药材底物与糖的配对路径）。

## 5. audit 结果

`python chemreact-staging/tools/audit_mapped_safety.py`：
- ERROR **0 处**
- WARN 13 个文件（均为既有脚本的本地重复实现，本轮未新增）
- mapped_chem 自检：通过 8，失败 0；退出码 0

UI 语法检查：`check_ui_js.py` 提取 2 个内联 script，`node --check` **2/2 通过**。
Python：templates.py / paozhi_adjuvants.py / chemreact.py / run_paozhi_smoke.py 全部 AST 通过。

## 6. 发现与限制（未改，如实记录）

1. ~~炮制档的「4 条规则」只约束 curated 规则层，SmartReact 基础模板库仍然参与~~
   → **已由 §8 的严格模式修掉**：炮制档默认只跑 4 条证据规则，基础模板库关闭；
   需要旧行为时显式加 `--paozhi-base-templates`。煎煮等非炮制档不受影响。
2. 辅料作「配对底物」时产物归在药材名下（见 §4 辅助说明），当前 CSV 无法逐条区分该配对，
   为避免编造指标，未新增「涉及辅料」字段；只保留可验证的「辅料作底物」计数。
3. 盐炙用 2% 食盐 + 杜仲 150°C/10 min；药典只给辅料量与「文火」，温度/时间来自单味药研究。
4. 姜炙档用 10% 生姜（药典量）+ 黄连 150°C/40 min；姜汁多成分、酒精度、醋的含水量均未建模。
5. 高压高温蒸制的循环参数（Molecules 2026）摘要未给，仍缺；不影响 A/B/C。
6. WebFetch 对多数域名返回「Unable to verify domain」，本轮改用 WebSearch + PowerShell/urllib 抓取
   （Europe PMC REST、Frontiers 全文 HTML、med66、万方），原文已存 `reports/_paozhi_src/`；不影响取数。

## 7. 阻塞项

无。A/B/C 所需数值与文献均取到；没有用「未取到」占位，也没有编造数值。

## 8. 严格模式（2026-10-31 追加，已设为默认；规则数已在 §9 扩到 11 条）

### 语义
- `炮制·*` 档默认 `use_base_templates=False`：SmartReact 基础模板库（9,770 条）不参与枚举，
  只跑 `rules/paozhi_evidence.json` 里的 4 条 curated 证据规则。
- 非炮制档（煎煮等）默认仍为 `True`，行为不变。
- 旧行为保留为显式开关 `--paozhi-base-templates`；开启后 meta 记
  `processing.strict=false`、`rule_scope=literature_backed_plus_base`。
- UI 不提供该开关（默认严格）；中文提示已改为「只跑有炮制文献证据的 4 条规则
  （SmartReact 基础模板默认关闭）」。（→ §9 之后提示语改为指向 `rules/paozhi_evidence.json`，
  不再写死规则数。）
- meta 的 `processing` 记录 `strict / base_templates / rule_scope / n_rules / rules`；
  `engine_notes` 增加 `base: 未启用（炮制严格模式）`。

### 严格模式后 smoke（甘草 limit 6，1 轮）
| 条件 | 产物（严格后） | 严格前 | 台账 `rule_name` 分布 |
|---|---|---|---|
| 炮制·盐炙 | 41 | 225 | 脱水 18、糖苷水解 17、酯水解 6 |
| 炮制·姜炙 | 41 | 225 | 同上 |
| 炮制·蜜炙（辅料开） | 44 | 298 | 脱水 21、糖苷水解 17、酯水解 6；辅料底物产物 3 |
| 炮制·醋炙（辅料开） | 41 | 367 | 脱水 18、糖苷水解 17、酯水解 6；辅料底物产物 0 |
| 炮制·醋炙（`--no-paozhi-adjuvant`） | 41 | 329 | 同上 |
| 炮制·醋炙（`CHEMCREACT_PAOZHI_ADJUVANT=0`） | 41 | 329 | 同上 |
| 守卫：煎煮（非炮制） | 705 | 705 | 基础模板、extra、mono 全部照旧 |

- `maillard_simplified_001` 已加载，但这批甘草运行里没有产物（不是被删，是规则未命中）。
- 蜜炙那 3 个辅料产物实测为葡萄糖/果糖自身的脱水（`elimination_dehydration_001`），
  不是糖与药材的配对反应。

### 旧行为可恢复（实测）
`--paozhi-base-templates` 跑蜜炙：产物回到 **298**，
`processing.strict=false / base_templates=true / rule_scope=literature_backed_plus_base`，
`rule_name` 重新出现 `esterification`（254 条）。

### 本轮检查
- AST：`smartreact_engine.py` / `query_base.py` / `chemreact.py` / `run_paozhi_smoke.py` 全部 OK。
- UI：`check_ui_js.py` 2/2 内联 script 通过。
- `audit_mapped_safety.py`：ERROR 0，WARN 13 个既有文件，自检 8/8。
- 未写 tcm.db、未动 `-wal`/`-shm`；未生成 PDF，未改论文稿。

### 严格模式带来的新限制
1. **P2 辅料共底物在严格模式下基本失效**：4 条证据规则全是单底物，
   乙酸/糖不能作为第二个底物进入反应；蜜炙的 3 个辅料产物只是糖自身被单底物规则处理。
   要让辅料真正参与，得补有文献证据的双底物规则——属于场景层，按约定留到最后。
2. 严格模式的产物数只反映现有 4 条证据规则的覆盖，不代表炮制化学全貌；
   碳化、异构化等仍记为「不可映射」。（→ 规则数已由 §9 扩到 11 条。）

## 9. 按文献补充炮制规则（2026-10-31 追加，用户明确授权）

用户原话：「补充吧，但是不能空口无凭的补，查找相关文献后再补规则。」

### 9.1 改了什么

严格模式规则数 **4 → 11**；`rules/rules.json` 新增 5 条、选入 1 条既有规则，
`rules/paozhi_evidence.json` 证据条目 **4 → 11**。

| 规则 id | 反应 | 条件档 | 文献依据（evidence 里的条目） |
|---|---|---|---|
| `hydrolysis_lactone_5ring_001` | 五元内酯开环（含 α,β-不饱和内酯） | hydrolysis | 郁红礼 等 2022，中国中药杂志 47(24):6596；HAO/JNB/FA 内酯开环 |
| `hydrolysis_epoxide_001` | 环氧开环 | hydrolysis | 同上；「结构中的环氧环容易开环」 |
| `esterification_acid_alcohol_001` | 乙酸 + 醇 → 乙酸酯 + H₂O | `esterification_paozhi`（新增档） | 同上；「有羟基时发生酯化成酯」，辅料醋提供乙酸 |
| `oxidation_allylic_alcohol_001` | 烯丙醇 → α,β-不饱和羰基 | thermal | 同上；「氧化成羰基」 |
| `demethylation_n_001` | 叔胺 N-脱甲基 → 仲胺 + 甲醛 | thermal | 李凯悦 2017，华西药学杂志 32(2):150-153；槟榔碱→去甲槟榔碱 |
| `decarboxylation_001` | β-二羧酸脱羧（限定丙二酸/β-二酸基序） | thermal | 安靖 等 2013，药物分析杂志 33(11):1910-1913；Danieli 1973 FEBS Lett |
| `cleavage_ether_acyclic_001` | 非环醚 C–O 断裂 | hydrolysis | 郁红礼 等 2022；二萜二聚体 EA 醚键断裂 → EHTA |

`rules.json` 新增 `esterification_paozhi` 条件档（20–200 °C，pH 0–14，水/醇/无溶剂，
酸或空催化剂）；6 条新规则全部标 `paozhi_only: true`，
`core/smartreact_engine.py` 在非炮制档（`curated_rule_ids is None`）跳过它们，
**煎煮等既有行为不变**。

### 9.2 规则级验证（真实结构，CLI 实跑）

结构来源：槟榔碱 HBIN016699、羧基苍术苷 CATR HBIN019719、JNB HBIN031562
均只读自 `tcm.db`；烯丙醇与乙醚为规则测试用简单底物。

| 底物 | 条件 | 命中规则 | 产物（分子式/结构） |
|---|---|---|---|
| 槟榔碱 C₈H₁₃NO₂ | 炮制·炒焦 | `demethylation_n_001` ×2 | 甲醛 `C=O` + 去甲槟榔碱 C₇H₁₁NO₂ `COC(=O)C1=CCCNC1` |
| CATR C₃₁H₄₆O₁₈S₂ | 炮制·炒黄 | `decarboxylation_001` ×2 | CO₂ + C₃₀H₄₆O₁₆S₂（ATR 骨架） |
| JNB C₂₀H₂₆O₄ | 炮制·醋炙 | `hydrolysis_epoxide_001` ×2、`hydrolysis_lactone_5ring_001` ×1 | 5 个产物，含 C₂₀H₂₈O₅ 两类开环产物 |
| 烯丙醇 | 炮制·醋炙 | `oxidation_allylic_alcohol_001` ×1 | 丙烯醛 C₃H₄O |
| 乙醚 | 炮制·醋炙 | `cleavage_ether_acyclic_001` ×1 | 乙醇 C₂H₆O |

脚本：`tools/_probe_paozhi_rules_20261031b.py`，`FAILURES=0`。

### 9.3 烟雾测试（甘草 limit 6，1 轮，严格模式）

| 条件 | 产物 | 相对 4 条规则时（41/44） | `rule_name` 分布 |
|---|---|---|---|
| 炮制·盐炙 | 42 | +1（内酯开环） | 脱水 18、糖苷水解 17、酯水解 6、内酯开环 1 |
| 炮制·姜炙 | 42 | +1 | 同上 |
| 炮制·蜜炙（辅料开） | 45 | +1 | 脱水 21、糖苷水解 17、酯水解 6、内酯开环 1；辅料底物产物 3 |
| 炮制·蜜炙（`--no-paozhi-adjuvant`） | 42 | +1 | 同上（无辅料） |
| 炮制·醋炙（辅料开） | **80** | +38（1 个与既有产物去重） | **乙酸酯化 39**、脱水 17、糖苷水解 17、酯水解 6、内酯开环 1 |
| 炮制·醋炙（`--no-paozhi-adjuvant`） | 42 | +1 | 无酯化 |
| 炮制·醋炙（`CHEMCREACT_PAOZHI_ADJUVANT=0`） | 42 | +1 | 无酯化 |
| 守卫：煎煮（非炮制） | **705** | 705 | 基础模板照旧；`paozhi_only` 规则未加载 |

- 乙酸酯只出现在「醋炙 + 辅料开」；盐炙/姜炙/蜜炙均为 0（不再把药材自身羧酸当酰基供体）。
- 39 行乙酸酯经 RDKit 结构检查：**0 个混合酸酐，39 个真酯**。
- `n_products_from_adjuvant=0` 是计数口径所致：乙酸作配对底物时产物归在药材名下；
  该字段只数「辅料自身作起始底物」的产物。

### 9.4 两个实测缺陷（已修，记录根因）

1. **`apply_pair` 只按 (a,b) 顺序匹配，不自动换向。**
   辅料乙酸总是追加在底物列表末尾（j 位），而规则原先把乙酸写成第 1 个反应物 →
   (甘草成分, 乙酸) 永远匹配不上，醋炙加辅料时 0 个乙酸酯。
   修法：SMARTS 反应物顺序改为「醇在前、乙酸在后」。
   实测：(葡萄糖, 乙酸) 6 个酯，(乙酸, 葡萄糖) 0 个。
2. **`[O;H1]` 把羧酸自身的 OH 也当成醇羟基。**
   甘草皂苷富含葡萄糖醛酸，旧写法生成 `CC(=O)OC(=O)-` 混合酸酐（46 行全是酐）。
   修法：醇羟基限定 `[O;H1;!$(O[C]=[O])]`，排除羧酸 OH。
   实测：乙酸+葡萄糖醛酸 → 5 个羟基乙酸酯、羧基不反应；醋炙 80 个产物中 39 行全为真酯。

### 9.5 仍然做不到的

1. **狼毒 herb-level 不能复现**：`tcm.db` 的狼毒（HERB003269，41 个成分）与月腺大戟
   （HERB006819，11 个）条目里没有 JNB、HAO、fischeria A、eupractenoid A 等名称，
   规则级验证用的是 PubChem / tcm.db 里的单体结构，不是整味药。
2. **条件数值没按案例调**：醋炙预设 84 °C/35 min（醋延胡索），文献狼毒醋制是
   160 °C/6% 乙酸/40 min；规则在 84 °C 档也会触发，属条件档差异，不是文献条件复现。
3. `time_min / pH / catalyst / dose` 仍不参与产物生成；只能做「某条件下会发生哪类反应」。
4. 只补了文献明确写出的 7 类反应；碳化、异构化、缩合仍记为「不可映射」。
5. 何首乌的缩合阶段仍未做（人参皂苷路径见 §10）。

## 10. 路径层验证（2026-10-31 追加）

用户验收口径第二条：文献中间体能在多轮枚举中出现。脚本
`tools/_probe_paozhi_paths_20261031.py`，种子结构只读取自 `tcm.db`，3 轮，`--max-pairs 400`。

| 案例 | 文献路径 | 实测结果 |
|---|---|---|
| **人参皂苷 Rb1**（HBIN027729） | Rb1 → Rg3 → Rg5/Rk1 | **完全复现**：r1 糖苷水解得 Rg3，r2 脱水得 Rg5 + Rk1；父代 SMILES 已核对 |
| 槟榔碱（HBIN016699） | → 去甲槟榔碱 | r1 命中（文献亦为一步） |
| CATR（HBIN019719） | → ATR | r1 命中（一步） |
| JNB（HBIN031562） | 内酯/环氧开环 | 分子式级命中 C₂₀H₂₈O₅，14 个同分异构候选，未做结构级区分 |

各轮产物数：Rb1 r1=15 / r2=119 / r3=759；arecoline r1=2；CATR 9/15/20；JNB 5/16/29。

**限制**：只有人参皂苷一条是真正的多步路径；引擎不做立体化学，
Rg3 的 20(R)/20(S) 共享同一 InChIKey 连接块；第三轮产物膨胀仍无收束。

**⚠ 口径修正**：本轮跑的是 `--max-pairs 400`。Rb1 第 3 轮前沿 119 个分子、
理论配对 7,021 对，**实际只跑 400 对**，meta `truncated: true`。
所以 r3=759 是截断结果，不是完整第三轮；且未开 `--fair-pairs`，截断偏向前排底物。
前两轮的路径结论（Rg3 在 r1、Rg5/Rk1 在 r2）不受影响。

### 10.1 「轮」是什么（用户 2026-10-31 问）

`core/query_base.py:562-651`：

- **一轮 = 一次迭代**，不是时间、不是温度、不是"一个反应"。
- 第 1 轮底物 = 输入成分；第 2 轮底物 = 第 1 轮**新增**分子；依此类推。
  原始输入只在第 1 轮参与（`frontier = new_this_round`）。
- 每轮内部跑「N(N-1)/2 个配对 × 全部双底物规则」+「每个底物 × 单底物规则」，
  所以是平方增长。
- **轮数是步数上界，不是等号**：一条规则可能一次改多个键，同一产物也可能更早由别的路径得到。

Rb1 实例：r1 底物 1 → 0 对、15 个新产物；r2 底物 15 → 105 对、119 个；r3 底物 119 → 7,021 对、只跑 400 对、759 个。

### 9.6 本轮检查

- AST：`smartreact_engine.py` / `chemreact.py` / 探针脚本全部 OK。
- JSON：`rules.json` 70 条（`paozhi_only` 6 条），`paozhi_evidence.json` 11 条，id 一一对应。
- UI：`check_ui_js.py` 2/2 通过；提示语不再写死「4 条」。
- `audit_mapped_safety.py`：ERROR 0，WARN 13 个既有文件，自检 8/8。
- 未写 tcm.db、未动 `-wal`/`-shm`；未生成 PDF，未改论文稿。
