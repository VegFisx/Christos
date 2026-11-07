# Christos 会话交接报告

日期：2026-10-29  
工作区：`D:\ProgramData\DSHNS`  
当前界面：`http://127.0.0.1:8765/`（HTTP 200，部署后进程 PID 25008，正在监听）

## 零、接手增量（已实现、部署并验证）

本次接手先以运行版 `D:\TCMAI\chemreact\ui.py` 和 `chemreact.py` 为基线，
将两份较新的后端机械同步回 staging，只有实际改动需要后续单独部署。

已完成：

1. 条件和具体物质分开留证。引擎仍接收 `water/aqueous`、`acid/base/metal`
   等粗类别，另存用户在界面实际选择的物质名：
   - `.meta.json` 顶层增加 `condition_details`
   - `out/runs.jsonl` 每批记录增加 `details.conditions`
   - HTML 报告和网页结果摘要显示实际物质
   - 同一结构中记录实际生效的温度、时长和 pH
2. 加入氦气 `He`、氖气 `Ne`、氩气 `Ar`。它们被归为“不提供氧/氢的载气”，
   只用于氧化还原门控，不宣称对所有反应绝对惰性。
3. 修复 `make_report.py` 中两个会阻止 HTML 报告生成的既有错误：
   样式字符串被误当成 `append` 的第二个参数；`detail` 局部变量遮蔽了明细列表。

实测（2026-10-29）：

- staging Web 备用端口 8767 提交成功：
  - 输入：苯甲醛，1 轮
  - 条件：5% 碳酸氢钠水溶液、25°C、60 分钟、pH 7、
    钯碳（Pd/C）、氩气（Ar）
  - 结果：11 个产物、11 条出处路径、11 个分子；报告正常生成
  - `.meta.json`、`runs.jsonl`、HTML 报告三处均含上述三个实际物质名
- 用户批准后，三份桥接文件已同步到 `D:\TCMAI\chemreact`，哈希逐一一致：
  - `ui_page.html`
  - `ui.py`
  - `chemreact.py`
- 线上 `8765` 用项目 venv 重启后复测成功：
  - 最终任务状态 `done`，退出码 0，总耗时 2.6 秒
  - 线上 HTML 报告 HTTP 200，实际物质名、25°C、60 分钟、pH 7 全部存在
- 首次重启曾误用系统 Python，子任务因缺少 RDKit 失败；已立即恢复为
  `D:\TCMAI\venv\Scripts\python.exe` 并复测通过。
- 惰性气体：`He/Ne/Ar` 下氧化、还原规则全部熄灭；`air` 允许氧化；
  `H2` 允许还原
- `test_conditions.py`：24 通过 / 0 失败
- `audit_template_chemistry.py`：16 通过 / 0 失败
- `run_regression_suite.py --fast`：6 个脚本，0 失败
- `audit_mapped_safety.py`：ERROR 0

部署状态：

- 用户已明确批准部署；只同步了实际改动的三份桥接文件，没有整套覆盖：
  - `ui_page.html`
  - `ui.py`
  - `chemreact.py`
- 引擎与报告代码均从 `D:\ProgramData\DSHNS\chemreact-staging` 直接加载，
  本次对 `core/query_base.py`、`core/smartreact_engine.py`、
  `conditions/model.py`、`tools/make_report.py` 的修改已在 staging 生效，
  不需要复制进 `D:\TCMAI`。

## 一、本轮完成了什么

### 1. 条件下拉改为具体物质

单味药页和方剂页都已修改，主要文件：

- `D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge\ui_page.html`
- 已同步部署到 `D:\TCMAI\chemreact\ui_page.html`

溶剂不再显示“水溶液”“有机溶剂”“油”等泛称，改为具体选项，例如：

- 水、0.9% 氯化钠水溶液、5% 碳酸氢钠水溶液
- 乙醇、甲醇、异丙醇、丙酮、乙腈、THF、1,4-二氧六环、乙酸乙酯、二氯甲烷、三氯甲烷、DMSO、DMF、甲苯、正己烷、石油醚
- 大豆油、橄榄油

催化剂不再显示“酸”“碱”“金属”“酶”等泛称，改为具体选项，例如：

- 盐酸、硫酸、乙酸
- 氢氧化钠、氢氧化钾、三乙胺、吡啶、碳酸钾、碳酸铯
- Pd/C、Raney Ni、氯化铁
- 脂肪酶、纤维素酶、β-葡萄糖苷酶
- 紫外光、可见光

这些泛称目前只保留为原生化下拉分组标题，不再是可选项。

### 2. 修复“自定义”条件无法运行

原问题：

1. 前端默认选择“自定义”。
2. 后端把“自定义”当成必须真实存在的条件档案名进行校验。
3. 模板库没有这个档案，任务在参数覆盖前直接退出。

修复内容：

- 在 `D:\ProgramData\DSHNS\chemreact-staging\conditions\templates.py:30` 新增“自定义”条件档案。
- 在 `ui_page.html:575` 和 `ui_page.html:604` 的单味药/方剂预设表中加入默认值。
- “自定义”默认值设为：
  - 溶剂：水
  - 温度：25°C
  - 时长：60 分钟
  - pH：7
  - 催化剂：无
  - 气氛：空气

这些只是中性工程默认值，不是药典标准，用户仍可逐项覆盖。

## 二、实测结果

已实际运行一个最小自定义条件任务：

```powershell
D:\TCMAI\venv\Scripts\python.exe -u D:\TCMAI\chemreact\chemreact.py predict `
  --herb 甘草 --limit 1 --rounds 1 --cond 自定义 `
  --solvent ethanol --temperature 80 --time-min 60 --ph 7 `
  --catalyst none --atmosphere air --no-report `
  --out D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge\out\custom-condition-test
```

实测结果：

- 任务成功，不再出现“条件档案‘自定义’不存在”。
- 输入：甘草 1 个成分。
- 产物：74 个。
- 枚举耗时：3.13 秒。
- 总耗时：3.5 秒。
- 输出文件：
  - `20261029-192716_甘草.csv`
  - `20261029-192716_甘草.tsv`
  - `20261029-192716_甘草.meta.json`

服务检查：

- `http://127.0.0.1:8765/` 返回 HTTP 200。
- 页面已包含具体溶剂、具体催化剂和“自定义”默认值。

注意：以上后端实测主动指定了乙醇、80°C、60 分钟、pH 7；中性默认值本身已通过模板导入和页面内容检查，但尚未做浏览器端视觉截图验证。

## 三、重要维护陷阱

### 不要盲目整套覆盖部署文件

当前 `D:\TCMAI\chemreact\ui_page.html` 与 staging 的 HTML 已同步且哈希一致，但：

- `D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge\ui.py`
- `D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge\chemreact.py`

这两份 staging 后端文件比正在运行的 `D:\TCMAI\chemreact` 版本旧。若为了部署而把三件套全部从 staging 复制过去，会覆盖正在运行版本中较新的代码。

移交后如果继续修改后端：

1. 先对比 `D:\TCMAI\chemreact` 与 staging 文件的哈希和差异。
2. 以正在运行版本为基线修改。
3. 只同步实际改动过的文件。

### 虚拟环境访问权限

`D:\TCMAI\venv\Scripts\python.exe` 的基础解释器位于工作区外。在沙箱中直接运行会出现“拒绝访问”或 `Unable to create process`。需要申请提权后运行，不是 Python 项目本身损坏。

## 四、已知事项与当前状态

### 1. 具体催化剂名称尚未进入溯源报告（staging 已完成，待部署）

界面现在显示“盐酸”“硫酸”“Pd/C”等具体名称，但为了保持规则门控兼容，前端仍向引擎传粗类别：

- 盐酸/硫酸/乙酸 → `acid`
- NaOH/KOH 等 → `base`
- Pd/C 等 → `metal`
- 各种酶 → `enzyme`

staging 现已把粗类别与实际物质名分开传递和留证：

- 引擎继续接收 `aqueous/acid/metal` 等粗类别，规则门控不失配
- 界面另传 `solvent_detail/catalyst_detail/atmosphere_detail`
- `.meta.json` 的 `condition_details` 同时保存 `category` 和 `detail`
- `runs.jsonl` 的 `details.conditions`、网页结果、HTML 报告均显示实际物质

运行版仍需按“只读源项目”规则取得部署授权，不能直接覆盖。

### 2. 稀有气体尚未加入（staging 已完成，待部署）

staging 的气氛现为：

- 无
- 空气
- O2
- N2
- H2
- He
- Ne
- Ar
- 真空
- CO2

`He/Ne/Ar` 仅被定义为“不提供氧/氢的载气”，不宣称对所有反应绝对惰性。
严格氧化还原门控已实测：三种气体下氧化和还原规则全部熄灭；空气允许氧化，
氢气允许还原。

### 3. 论文与参考文献事项（已完成联网核验）

2026-10-29 已补齐并核验：

- TDC：Huang et al. 2022,
  DOI `10.1038/s41589-022-01131-2`
- CTD：Davis et al. 2026,
  DOI `10.1093/nar/gkag1041`
- Tox21：Richard et al. 2021,
  DOI `10.1021/acs.chemrestox.0c00264`
- ToxCast：Richard et al. 2016,
  DOI `10.1021/acs.chemrestox.6b00135`
- OnSIDES：Tanaka et al. 2025,
  DOI `10.1016/j.medj.2025.100642`
- 药典 2025：官方书目 + `Independent-KBs` 固定提交
  `63cfd6a`

已更新：

- `reports/paper/DATA_CARD.md`
- `reports/paper/arxiv-20261020/manuscript-humanized.md`
- `reports/paper/Christos-system-paper-draft-20261019-zh-humanized.md`
- 对应 HTML/PDF 已重新生成
- 外部响应、状态码和 SHA-256 快照存于
  `reports/paper/reference_verification_20261029/`

必须保留的边界：

1. `admet_cache.db` 未保存 TDC 发布标签，只能写 TDC-derived cached snapshot；
2. Tox21/ToxCast 来自同一缓存，本地也没有独立版本号；
3. OnSIDES v3.1.1 已留存但未进入头条结果；
4. `Independent-KBs` 未声明仓库级许可证，药典 overlay 仅限内部使用。

### 4. PeerJ-oriented English rewrite

2026-10-30 下载并阅读了 4 篇 PeerJ 全文，覆盖天然产物数据库、显式溶剂构象
搜索、天然产物敏感性预测和致敏性机器学习。全文与 Crossref 元数据存于：

`reports/paper/peerj_style_samples_20261030/`

新英语稿：

- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.md`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.html`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.pdf`

重写保留原有数值、表格和 18 条参考文献；摘要改为 PeerJ 常见的
Background / Methods / Results / Conclusions 结构，正文由 7,331 词压到
6,201 词。已清除粗体装饰、em dash、en dash、`not X but Y` 和重复 closer。
通讯作者改为 `[To be completed]`，旧通讯邮箱及通讯作者标注不再出现在新稿中。

原 `manuscript-humanized.*` 和历史 PDF 保留不动，避免覆盖既有版本。

2026-10-30 又按同一结构生成了中文版：

- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.md`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.html`
- `reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030-zh.pdf`

中文版保留与英文新版相同的数值、表格和 18 条参考文献；通讯作者同样为
`[待填写]`。`paper-zh.css` 增加了图片宽度约束，避免架构图越出 A4 版面；
含行内代码的段落改为左对齐并允许路径换行，避免两端对齐把空格拉散。

用户提供的 AI 检测截图命中若干中文段落后，中文正文又做了一轮段落级改写：
拆分模板化长句，减少重复连接词和均衡排比，并把讨论、评价设计、转化检查、
局限和结论改写成更具体的观察顺序。数值和 18 条参考文献未改。
英文稿随后按同一段序和语气同步，并重新生成 HTML/PDF。两版继续使用
`[To be completed]` / `[待填写]` 作为通讯作者占位。

### 5. Literature consistency validation

2026-10-30 新增 `tools/validate_literature_conversions.py`，用当前引擎重跑
5 个文献案例，并记录目标产物、匹配规则、反应中心、分子式差、文献中间体、
PubChem 立体结构核对和本地执行时间。

结果：

- 产物连接层命中：5/5
- 使用预期水解规则：5/5
- PubChem 立体结构重跑完整命中：1/5
- PubChem 连接层命中：5/5
- Ginsenoside Rd 和 isoquercitrin 中间体继续生成目标：是

已加入中英文论文的方法、结果、局限、结论、数据可用性和参考文献。
新文献快照存于 `reports/paper/reference_verification_20261030/` 和
`reports/paper/literature_validation_fulltext_20261030/`。

## 五、建议新会话开场提示

可直接把下面这段发给新会话：

> 请先阅读 `D:\ProgramData\DSHNS\AGENTS.md` 和
> `D:\ProgramData\DSHNS\chemreact-staging\reports\SESSION-HANDOFF-20261029.md`。
> 当前运行版在 `http://127.0.0.1:8765/`，staging 在
> `chemreact-staging\integration\tcmai_bridge`。运行版与 staging 已完成具体物质留证、
> He/Ne/Ar 气氛门控和报告生成修复，并通过 Web 链路与快速回归。
> 后续若再部署，按“D:\TCMAI 只读”规则仍须取得用户明确授权，
> 且只同步实际改动文件，不能整套覆盖。

