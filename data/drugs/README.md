# ChEMBL 批准药物快照

这个目录是 **ChEMBL 的离线只读快照**，供 `sources/drug.py` 与
`integration/tcmai_bridge/chemreact.py --drug/--drug-file` 使用。
快照里的结构全部来自 ChEMBL API；**没有手写 SMILES**。

## 当前快照

| 项 | 值 |
|---|---|
| 版本 | `ChEMBL_37` |
| 发布日 | 2026-05-01 |
| 抓取方式 | `tools/fetch_chembl_drugs.py`（ChEMBL REST API） |
| API 命中 | 4,225 条 `max_phase=4` |
| 保留 | 3,311 条 `molecule_type=Small molecule` 且有结构 |
| 排除 | 808 条无结构 + 106 条非小分子 |
| 盐/衍生物 | 1,114 条（`parent_chembl_id != chembl_id`） |
| 已撤市标记 | 338 条（保留并标注，不自动排除） |
| 天然产物标记 | 1,839 条（ChEMBL `natural_product`） |
| 文件 | `chembl_37_drugs.jsonl`（JSONL，一行一个药物） |
| 元数据 | `chembl_37_meta.json`（版本、字段、SHA-256、许可证） |

`max_phase=4` 表示 ChEMBL 口径的「已批准」，**不等于当前仍在销售**；
`withdrawn` 字段单独保留，使用时请自行判断。

## 许可证与引用

ChEMBL 数据由 EMBL-EBI 提供。按 2026-11-23 访问 ChEMBL 官网
（<https://www.ebi.ac.uk/chembl/>）时的声明，采用
**Creative Commons Attribution-ShareAlike 3.0 Unported（CC BY-SA 3.0）**
许可：<https://creativecommons.org/licenses/by-sa/3.0/>。

使用本快照或由其产生的衍生数据时，请保留署名并同样以 CC BY-SA 3.0
共享衍生数据。许可证以 ChEMBL 官网当前声明为准；建议引用：

- ChEMBL: <https://www.ebi.ac.uk/chembl/>
- 具体版本：`ChEMBL_37`（2026-05-01）
- 元数据文件 `chembl_37_meta.json` 中有完整字段与 SHA-256。

## 已知限制

1. **只含小分子**：蛋白、抗体、寡糖等 `molecule_type` 不是
   `Small molecule` 的批准药物被排除（106 条）。
2. **只含 ChEMBL 有结构记录者**：808 条 `max_phase=4` 记录没有
   `canonical_smiles`，无法作为反应底物。
3. **盐型与母体并存**：1,114 条是盐/衍生物。按名称解析时优先母体；
   具体条目请用 ChEMBL ID 指定，避免把盐型与母体混为一谈。
4. **InChIKey 立体层差异**：3,311 条中有 5 条（0.15%）ChEMBL 的
   `standard_inchi_key` 与由 `canonical_smiles` 重算的完整 InChIKey
   在立体层不同（骨架前 14 位一致；涉及 porphyrin / cefotetan 类结构）。
   本项目以 ChEMBL 的 `canonical_smiles` 作为反应输入，并在测试中报告
   该差异；不手改结构。
5. **药物不是医疗建议**：这里只做化学反应枚举，输出是候选化学产物，
   不是疗效、安全性或临床结论。

## 刷新

```powershell
D:\TCMAI\venv\Scripts\python.exe -I -X utf8 tools\fetch_chembl_drugs.py
D:\TCMAI\venv\Scripts\python.exe -I -X utf8 tools\test_drug_source.py
```

脚本会用新版本号生成 `chembl_<N>_drugs.jsonl` / `_meta.json`，不会覆盖旧快照；
默认加载版本号最大的快照。不要手工编辑 JSONL；需要修改字段就改抓取脚本并重抓。

## 字段

`chembl_id`, `name`, `smiles`, `inchi`, `inchi_key`, `formula`, `mw`,
`heavy_atoms`, `max_phase`, `first_approval`, `molecule_type`,
`structure_type`, `parent_chembl_id`, `active_chembl_id`, `synonyms`,
`natural_product`, `oral`, `parenteral`, `topical`, `black_box_warning`,
`withdrawn`, `availability_type`, `source`。
