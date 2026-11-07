# 第一百一十四轮：extent 温度项换成 Arrhenius

> 一句话：把「温度每升 10 °C 速率乘 2」的经验式换成 **Arrhenius（Ea = 103.6 kJ/mol，实测）**，Q10 保留作回退开关。**参照温度上的数字一个没变**，低温端更符合实验（80 °C 从 0.221 降到 0.140）。

---

## 1. 为什么换

第一百一十三轮标定发现：同一反应（人参皂苷 Rb1 水解）在不同温度区间的 Q10 是 **1.52 与 3.67**，两条独立研究给出 **1.86** 和 **2.60**。用一个固定 Q10=2 去跨越 80→105 °C，本质是把「10 °C 内的经验近似」硬拉到 25 °C 跨度上。

Arrhenius 形式 `k(T)/k(T_ref) = exp(-Ea/R·(1/T − 1/T_ref))` 里 Ea 是物理量，跨温度不需要分段修正 —— 而且**这次已经有实测值**（103.6 kJ/mol），符合 AGENTS §十二 的要求。

## 2. 改了什么

| 文件 | 改动 |
|---|---|
| `conditions/kinetics.json` | 新增 `arrhenius` 块：`enabled: true`、`ea_kJ_per_mol: 103.6`、`ea_range_kJ_per_mol: [68.0, 103.6]`、`R: 8.314462618`、`status: literature_single_study`，附来源 DOI `10.3831/KPI.2020.23.012`、表号与原文引句；`q10` 块保留（`enabled=false` 时回退） |
| `conditions/extent.py` | 新增 `_arrhenius_ea()` 与 `temperature_factor(T, T_ref, params)`；`_extent_core` 改用它；`extent_from_profile` 的 `why` 文案写明「温度按 Arrhenius（Ea=103.6 kJ/mol）」或「Q10 经验式」；模块口径文档同步 |
| `tools/test_condition_extent.py` | 新增第 10 节共 **11 条**断言（手算吻合 4 个温度、参照点=1、单调、极端值截断、回退路径、why 文案） |
| `reports/kinetics_calibration_20261106.json` | 未改（拟合结果只读） |

安全措施：因子夹在 `[1e-6, 1e6]`；`T` 转开尔文后 ≤0 直接返回 1.0；`ea` 缺失或非正 → 自动回退 Q10。

## 3. 新旧对照（同一条件，参照 100 °C / 60 min）

| 条件 | 旧（Q10=2） | 新（Arrhenius） | 说明 |
|---|---|---|---|
| 100 °C / 60 min | 0.632 | **0.632** | 参照点，刻意保持不变 |
| 80 °C / 60 min | 0.221 | **0.140** | 低温端更陡，符合实测（80 °C k 只有 100 °C 的 15 %） |
| 60 °C / 60 min | 0.062 | **0.018** | 同上 |
| 25 °C / 60 min | 0.004 | **0.0002** | 室温糖苷水解实际可忽略 |
| 121 °C / 60 min | 0.986 | **0.997** | 高温端趋于饱和，两者都接近 1 |
| 100 °C / 5 min | 0.080 | 0.080 | 时间项未动 |
| 100 °C / 1440 min | 1.000 | 1.000 | 同上 |

时间的单调性、档位边界（0.10 / 0.50）都没变。

## 4. 对产物的影响

**零**。`kinetics.json` 的 `validation.gate_enabled` 仍是 `false`，`extent.gating_allowed()` 仍返回 `False`，extent 只写标注、不参与过滤。所以：

| 检查 | 结果 |
|---|---|
| 炮制 8 场景烟雾 | **43 / 43 / 46 / 43 / 81 / 43 / 43 / 824**（与基线逐项一致） |
| `tools/test_condition_extent.py` | **ALL PASS（45 条，含新增 11 条）** |
| `tools/test_kinetics_measurements.py` | ALL PASS（8 条） |
| `tools/audit_mapped_safety.py` | ERROR 0 / WARN 13 / 自检 8 通过 |

顺带修掉一个测试自身的坑：`extent.load_params()` 返回**缓存对象**，测试里直接改它会让后面的断言读到被污染的全局状态（表现为「Arrhenius 突然变成 Q10」）。已改成 `deepcopy` 后再改。

## 5. 局限（写清楚，别当成精确模型）

1. **Ea 只有一条研究**（人参皂苷水解，水/蒸汽基质）。不同反应族的 Ea 不同 —— 酯水解、脱水、氧化的 Ea 通常差一倍以上。当前是「全反应族共用一个 Ea」，属于**近似**。
2. 另一条数据（80 % 甲醇、纯标准品）给 68.0 kJ/mol，两者差 35 %，说明基质效应很大；已登记为区间下界，不参与默认计算。
3. 干热路径（炒黄/炒炭）的脱水/异构化不能用这条 Ea（那条 Q10=4.26、Ea=215.7 是热稳定性，不是水解）。
4. `extent_min = 0.10` 仍然没有出处（第一百一十三轮 §8 已记）。

## 6. 下一步（若继续，按性价比排）

1. **per-profile Ea**：`rules/*.json` 的 `condition_profile` 里加可选 `ea_kJ_per_mol`，缺失才用全局值。这样酯水解/脱水各用各的。
2. 补 2~3 条水相 80–100 °C 的糖苷/氰苷水解时间序列，把 68 vs 103.6 这个分歧压下去。
3. `extent_min` 的判据来源（"多少算发生了"）需文献明确表述，否则永久保持门控关闭。

## 7. 复现

```powershell
$env:PYTHONIOENCODING='utf-8'; $PY='D:\TCMAI\venv\Scripts\python.exe'
cd D:\ProgramData\DSHNS\chemreact-staging
& $PY -I tools\test_condition_extent.py          # 45 条
& $PY -I tools\run_paozhi_smoke.py                # 8 场景
# 关掉 Arrhenius 复现旧数字：把 conditions/kinetics.json 的 arrhenius.enabled 改成 false
```
