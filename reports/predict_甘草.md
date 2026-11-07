# 甘草 —— 成分间反应预测（双源）

- 数据源：`tcm.db` + `coconut.db` **双源**（`collect_compounds`），真实数据非手写
- 双源去重后**可用成分 1204 个**（HERB 361 + COCONUT 843）
- **本次实际取用 120 个 = 可用量的 10.0%**（HERB 按分子量降序、COCONUT 按 np_likeness 降序，两源各半）
- 两两配对 **7140** 对；规则库 SmartReact **9770** 条模板
- 去重后预测产物 **59653** 个
- **命中已知天然产物 0 个**（COCONUT 参照库 269,105 个 + tcm.db 29,013 个）

## 一、本次触发的反应类型及其反应条件

条件来自 **ORD 真实实验数据**（统计被该类型复现的反应实际用了什么），非手写；无数据会明确标注。**条件只作标注，不筛除任何反应。**

| 反应类型 | 参与的配对数 | 该类型产物数 | 反应条件（来自 ORD） | ORD证据数 |
|---|---|---|---|---|
| `esterification` | 15 | 35521 | 温度 36.0°C（0.0~130.0，n=25）；时间 8.0 小时（n=76）；溶剂 dichloromethane / ethyl acetate / chloroform；催化剂 4-dimethylaminopyridine / DMAP / sulfuric acid；**辅助试剂** sulfuric acid / thionyl chloride / HCl | 190 |
| `mitsunobu` | 15 | 24126 | 温度 4.0°C（-5.0~70.0，n=29）；时间 3.0 小时（n=77）；溶剂 THF / tetrahydrofuran / toluene；催化剂 acetic acid；**辅助试剂** triphenylphosphine / diethyl azodicarboxylate / tributylphosphine | 130 |
| `horner_wadsworth_emmons` | 1 | 6 | **无 ORD 条件数据** | 0 |

## 二、命中【已知天然产物】的预测产物（最强证据）

（本次无命中）

## 三、置信度最高的预测产物（多模板共识，前 40）

| 产物 | 分子式 | 分子量 | 模板数 | 命中 | 反应类型 |
|---|---|---|---|---|---|
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)O)CC2C3=CCC4C5(C)CCC(OC6OC(C(=` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)OC2C(C(=O)O)OC(OC3C(OC4CC(C)(C` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)OC2C(C(=O)O)OC(OC3CC(C)(C)C4CC` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)OC2C(C)OC(OC3C(OC4C(OC5CC(C)(C` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)OC2C(O)C(C(=O)O)OC(OC3C(OC4CC(` | C100H150O41 | 2008.3 | 1 |  | esterification |
| `CC(=O)OC1CC(C)(C(=O)OC2C(O)C(C(=O)O)OC(OC3CC(C)(C)` | C100H150O41 | 2008.3 | 1 |  | esterification |

---

## 这个工具能做什么、不能做什么

**能**：对给定药材，从 **tcm.db + COCONUT 双源**取真实成分，穷举两两之间的单步反应，给出产物、反应类型、**ORD 实测条件**，并把产物回查 **27 万个已知天然产物**作佐证。

**不能**（重要）：

1. **只覆盖单步、双组分**反应。多步级联、三组分以上、分子内环化做不到。
2. **对真实文献反应覆盖率约 30%**（ORD 177 万条实测）→ 没预测出来 ≠ 不会发生。
3. **条件只标注、不做筛选**（按用户 2026-10-11 要求）→ 产物里会有**化学上不可能**的（如无 PPh₃ 的 Mitsunobu）。这是已知缺陷。
4. **不判断热力学/动力学可行性**。能枚举 ≠ 真会发生。
5. **无假阳性率数据**（缺负样本），无法给精确率。

明细：`predict_甘草.csv`
