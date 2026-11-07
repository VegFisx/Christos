# 第十四轮 / 任务③：TCMAI 接入方案（2026-10-12）

> 纪律：`D:\TCMAI` **只读**。本文只给方案 + 只读演示结果；补丁要用户确认后才动。

---

## 一、结论先说

| 项 | 状态 |
|---|---|
| 技术可行性 | **已就绪**：`integration/tcmai_bridge.py` 可直接 import，接口与 `tcm_analyzer.predict_reactions()` 同形状 |
| 只读演示 | **已跑通**：甘草 40 成分 / 煎煮 100 °C → **3,444 个产物（全部 esterification，MW 709–2008）** |
| 是否现在正式接 | **我的建议：先别**。本轮 HTE 实测的可信度是 **召回 64% / 假阳性 94.9% / 条件门控 AUC 0.530**。接进去 = 把"高召回、低精度"的候选清单当预测给用户 |

**如果要接，建议接成实验性开关（默认关）**，并把下列三个数字随输出一起落盘。

---

## 二、最小补丁（需确认后才动 `D:\TCMAI`）

| 文件 | 改什么 | 为什么 |
|---|---|---|
| `src\tcm_analyzer.py` | 新增 `predict_reactions_v2(compounds, conditions)`，内部调桥；旧函数保留 | 旧版 10 条手写 SMARTS；新版是 9,770 模板 / 37 类 + 条件门控 |
| `src\cascade_reactions.py` | `_irreversible_rules()` 改读桥的 `get_reactions()` | 桥返回的 `irreversible` 标记按 `integration/tcmai_bridge.IRREVERSIBLE_CLASSES`（**我的建模选择，需复核**） |
| 依赖安装 | 把 `chemreact-staging/libs/smartreact`、`core/smartreact_engine.py`、`conditions/`、`reports/conditions_normalized.json`、`reports/aux_reagent_coverage.json` 拷进 TCMAI（或把 staging 加进 `sys.path`） | rdkit 已有（同一 venv `D:\TCMAI\venv`） |
| （可选）`src\thermo_filter.py` | 把 `activation` 分数纳入排序 | 条件门控分数比"全或无"更细 |

**不能只换 `get_reactions()` 就完事**：本引擎每个反应类型背后是几十~上千条模板，
**没有单一 `rxn`（ReactionFromSmarts）对象**，所以 `rinfo["rxn"].RunReactants(...)`
这条路必然要换成 `predict_reactions()`。

---

## 三、接口映射（实测自 `tcm_analyzer.py:288-352`）

| TCMAI 旧字段 | 桥的对应 | 说明 |
|---|---|---|
| 输入 `compounds: list[dict]` | 同 | 键 `smiles` / `name` / `herb_name`（或 `source`） |
| `from_herb` | `p.source_herb` | 一致 |
| `from_compound` | `p.source_name` | 一致 |
| `rxn` | `p.rule_name` | 37 类之一（旧版是 10 条手写规则名） |
| `formula` / `smiles` / `mw` | `p.formula` / `p.smiles` / `p.mw` | 一致 |
| —— | **`activation`**（新增） | 条件门控分数 0~1 |
| —— | **`category`**（新增） | 反应类别 |
| `get_reactions()` 的 `rxn` 对象 | **无对应** | 见上：必须换调用方式 |

---

## 四、风险与限制（必须随接口一起交付）

1. **假阳性 94.9%**（HTE 1,993 个实测全 0 收率底物对，引擎声称能发生 1,891 个）。
   → 输出的产物**大部分是"结构上可能、实验上不发生"**，必须标成候选。
2. **召回 64%**（HTE 正对照 2,500 条）与 **ORD 泛化命中 28.6%**。
   → 没预测出来 ≠ 不会发生；预测出来了 ≠ 会发生。
3. **条件门控 AUC 0.530**（459 个同底物不同条件的对比，353,509 次比较）＝ 几乎无判别力。
   → 别人问"换个溶剂会不会不同"，现在的答案是"我区分不出来"。
4. 演示里 40 个成分炸出 3,444 个产物，需要 TCMAI 侧的排序/限额（旧版 `RULE_LIMITS` 只对 10 条规则有意义）。
5. 逆合成那条线（形式 80% / 化学可用 44%）与本桥无关，是另一个入口。

---

## 五、接入后的验收清单

```powershell
# 1) 只读演示（现在就能跑）
D:\TCMAI\venv\Scripts\python.exe chemreact-staging\integration\tcmai_bridge.py --demo 甘草
# 2) 可信度数字随接口打印
D:\TCMAI\venv\Scripts\python.exe chemreact-staging\integration\tcmai_bridge.py --confidence
# 3) 只读纪律校验：D:\TCMAI 下不得有本会话写入的文件；data\xtb_cache 仍 7 个
# 4) 与旧 predict_reactions 的产物数/类型对比（产物数会暴涨，口径需用户确认）
```

## 六、我建议的落地顺序

1. 先做**只读集成演示**（本模块，已完成）→ 让用户看到产物清单长什么样、量级差多少；
2. 用户确认"要的是候选清单"之后，再改 `tcm_analyzer.py`（加 v2 函数 + 开关）；
3. 最后才考虑进 `dist/`（打包）与 UI。
