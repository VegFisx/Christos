# E：辅助试剂接进门控 —— 报告（2026-10-11 第十一轮）

> **上一轮的门控只知道温度和溶剂；这一轮把「试剂」也接进去了。**
> 实测：给 PPh₃ 时 `mitsunobu` 放行，给无关试剂时降权到 0.5，不给试剂时不检查（向后兼容）。

---

## 一、为什么上一轮没做、这一轮卡在哪

上一轮结束时我写了三条欠账，第一条是：**辅助试剂数据已经规范化好了，但没接进门控**。
数据确实在（`conditions_normalized.json` 的 `auxiliary_reagents`），但接的时候卡在一个具体问题上：

**条件表里存的是名字（`triphenylphosphine`），调用方给的是 SMILES。**
第一次实现直接拿两边去 `MolFromSmiles`，`MolFromSmiles('triphenylphosphine')` 返回 `None`，
匹配**必然失败**。实测表现是「给了 PPh₃，mitsunobu 还是被判 0.5」——
看起来像门控太严，其实是名字没解析。

修法：加一张**名字到 SMILES 的别名表**（`REAGENT_ALIAS`，35 条常见试剂），
匹配时先做别名替换再 canonical 化，最后才退回字符串匹配。

---

## 二、做法

### 2.1 模型层：`Conditions` 加 `reagents` 字段

旧模型只有单个 `reagent: Optional[str]`，装不下「Mitsunobu 要 PPh₃ + DEAD」。
新增 `reagents: Tuple[str, ...] = ()`，并加 `has_reagent()` 做归一比对。
旧字段保留不动，**向后兼容**。

### 2.2 门控层：`cond_activation()` 增加试剂判据

```
条件里没写试剂   -> 不检查（保持 1.0）
条件里写了试剂   -> 与该类反应的 ORD 常用试剂 top-8 比对
                     命中任一 -> 维持分数
                     一个都不命中 -> 降权到 0.5
```

**「没写试剂就不检查」是有意的**：否则默认条件下（比如煎煮就是水），
所有需要试剂的反应都会被一次性拦掉，等于把门控变成全关。

---

## 三、实测

### 3.1 逐场景判定

| 条件里的试剂 | mitsunobu | suzuki | amide_coupling |
|---|---|---|---|
| 不给 | 1.00 | 1.00 | 1.00 |
| **只给 PPh₃** | **1.00** | 0.50 | 0.50 |
| 给 PPh₃ + DEAD | 1.00 | 0.50 | 0.50 |
| 给无关试剂（乙醇） | 0.50 | 0.50 | 0.50 |

**`mitsunobu` 只在有 PPh₃ 时得到满分**，其他类型不会因为 PPh₃ 而放行 —— 判据是对的。

### 3.2 真实底物：试剂真的会改变产物

12 个中药成分（tcm.db，150~400 Da）：

| 条件 | 产物数 | 出现的反应类型 |
|---|---|---|
| 煎煮 100°C，无试剂 | 17 | amide_coupling / esterification / reductive_amination×2 |
| 煎煮 100°C + PPh₃ | 17 | 同上（**mitsunobu 仍被温度门控拦掉**） |
| **室温 THF + PPh₃ + DEAD** | **23** | 上面 4 类 **+ mitsunobu** |

这行数据同时验证了**两道门是独立生效的**：
- 温度门控：100°C 水相下，给了 PPh₃ 也不会触发 mitsunobu（ORD 实测上限 70°C）；
- 试剂门控：室温 THF 下，给了 PPh₃ + DEAD 才会出现 mitsunobu。

### 3.3 回归验证（确认没破坏上一轮）

重跑上一轮的条件门控测试，所有数字**完全一致**：

| 条件 | 产物数（上轮 / 本轮） | 判零类型数 |
|---|---|---|
| 室温水浸 | 16 / 16 | 4/37 |
| 煎煮 100°C | 11 / 11 | 2/37 |
| 乙醇回流 | 16 / 16 | 2/37 |
| 高温久煎 | 1 / 1 | 20/37 |
| 低温冷浸 | 16 / 16 | 5/37 |

**新判据没有误伤旧行为。**

---

## 四、还剩什么

1. **试剂判据只有「命中/不命中」两档**，没有「必需件」概念。
   想做「Mitsunobu 缺 DEAD 就判零」，需要**每个试剂的覆盖率**
   （即多少比例的 Mitsunobu 反应用了 DEAD）。
   我写了统计脚本 `tools/extract_aux_reagent_coverage.py`，但它要逐条枚举归类 20 万条反应，
   **太慢**（跑了 5 分钟没进展，已停）。要做的话得改成并行分片（工作区已有这套做法）。
2. **溶剂词表仍然只有 8 个粗类别**（DMF/DCM/THF 全压成 `organic`）；
3. **反例数据仍然是原理性空缺** —— 门控减少假阳性，但算不出准确率。

---

## 五、产物

| 文件 | 内容 |
|---|---|
| reports/reagent_gate_test.txt | ★ 试剂门控实测（逐场景 + 真实底物） |
| reports/condition_gate_regress.txt | ★ 回归验证（与上一轮完全一致） |
| tools/test_reagent_gate.py | 试剂门控测试 |
| tools/extract_aux_reagent_coverage.py | 覆盖率统计（太慢，未跑完，留作后续） |
| conditions/model.py | ★ `reagents` 字段 + `has_reagent()` |
| core/smartreact_engine.py | ★ `REAGENT_ALIAS` / `_reagent_key` / 试剂判据 |

