# 第十七轮 · ORD 条件门控【误杀率】（false negative）实测

数据源 `chemreact-staging\reports\ord_condition_dataset\shard_*.parquet`（178 分片 / 925,943 行，**只读**）。
标尺：ORD 每条都是真实做过、有收率的反应 =「真·会发生」；测的是 HTE【假阳性 94.9%】的反方向。

## 结论先行

1. ★ **误杀率 = 0.67%（5/742）**【实测】（15000 行抽样，B 相对 A 少命中 5 条；缺省温度换成室温 25 ℃ 后降到 **0.13%（1/742）**，见 §四）。有真实温度子集 **1.16%（1/86）**；温度缺失子集 **0.61%（4/656）**；0 ℃ 冰浴子集 **0%（0/9）**。
2. ★ **5/5 全是「容差边界衰减到恰好 0.0 被当成判零」**，无一条来自真正超窗：`cond_activation()` 在 `[lo-30, hi+30]` 内线性衰减，到边界正好 `0.0`，而 `step()` 把 `act <= 0.0` 一律丢弃（原因串却写"降权"）。4 条更巧：温度缺失 -> 缺省 100 ℃，恰好 = mitsunobu 上限 70 + 容差 30 = 100。【推断】衰减留 0.05 下限即可消掉这 5 条。
3. **方向对比**：HTE 假阳性 94.9% ↔ ORD 误杀 0.67%。门控**不是**主要风险源；当前最大的"漏"是**模板覆盖**：A 就有 **71.3%（3203/4495）** 记录一个产物都枚举不出（与门控无关，门控只判零 0.40%）。
4. **配置 C（自抽模板默认开）**：命中 20.96% vs A 16.51%，相对 B 净 **+205 条、丢 0 条** -> 提召回不增误杀；C 的误杀仍是同一批 5 条。
5. ⚠ **试剂门控的误杀本次测不到**：ORD 该数据集没有 REAGENT 角色（可得率 0%，`reagents` 只能传空）-> 引擎走"没写试剂不检查"分支。0.67% 只是**温度门控**的误杀率【实测】。
6. ⚠ **命中率与收率反向**【实测】：收率 <30% 的 A 命中 22.3%，>80% 的只有 11.9%（高收率文献多是大分子/特殊催化，模板覆盖更差）。

## 一、口径（写死，先定再测）

- **抽样**：duckdb `read_parquet('shard_*.parquet') USING SAMPLE N ROWS (reservoir, 20261013)` —— **按【行】在 178 分片上均匀抽，非按片抽**；主结果 N=15000（覆盖 178/178 片，最集中一片 121 行），`id_hash(sorted reaction_id)=5cbb696c0476`；同 seed 重跑一致【实测】。**筛选**（逐条判定、先命中先计数）：产物空 / 产物不可解析 / 无 REACTANT SMILES / **REACTANT<2** / **REACTANT>2** / 底物不可解析 / (产物,底物集) 去重 -> 其余入评测集；REACTANT 数取自 `reactant_smiles_components`（分号分隔），**不用** `reactants_n`（见坑 5）。
- **条件**：记录的 `temperature_C` / `solvent_names[0]` / `catalyst_names`（关键词归 metal/acid/base/enzyme/light【推断】）构造 `conditions.model.Conditions`；`reagents` 一律空。★ 温度缺失**不当 0 ℃**：单列 `S_notemp`、用缺省 100 ℃（引擎默认）跑【推断】，另有 25 ℃ 敏感性（§四）；0 ℃ 是真实冰浴，按 0 传入并单列 `S_ice`（S_ice ⊂ S_temp ⊂ S_all = S_temp + S_notemp）。
- 【实测·代码审查】`catalyst` 在 `cond_activation()` 里出现 0 次、溶剂只能降权到 0.6 -> 二者对命中/判零无影响，**只有温度能判零**。**命中**：记录产物 `mapped_chem.canon_plain` 出现在 `step()` 返回产物集合里。**门控判零（主口径）**：A 有产物而 B 无产物（A/B 模板集相同，只差门控开关 -> 这个差就是"该对枚举结果被门控全判零"）；旁证口径 `stats["gated_zero_total"]>0 且本次返回 0 产物`（逐条一致）。
- **三配置（显式传参，不依赖默认值）**：A=`use_extra_templates=False,gate_conditions=False`；B=`False,True`；C=`True,True`。

## 二、三配置对比（15000 行抽样 seed=20261013；★ 绝对数 + 百分比）

| 子集 | A 纯模板库 | B 模板库+门控 | C 当前默认 | B 判零(主口径/计数器) | A 零产物记录 |
|---|---|---|---|---|---|
| **S_all** n=4495 | **742 (16.51%)** | **737 (16.40%)** | **942 (20.96%)** | 18 (0.40%) / 18 | 3203 (71.3%) |
| **S_temp** n=932 | 86 (9.23%) | 85 (9.12%) | 130 (13.95%) | 6 (0.64%) / 6 | 736 (79.0%) |
| **S_notemp** n=3563 | 656 (18.41%) | 652 (18.30%) | 812 (22.79%) | 12 (0.34%) / 12 | 2467 (69.2%) |
| **S_ice** n=116 | 9 (7.76%) | 9 (7.76%) | 15 (12.93%) | 0 (0%) / 0 | 96 (82.8%) |

| ★ 关键数字【实测】 | S_all | S_temp（有温度） | S_notemp（缺温度，缺省 100 ℃） |
|---|---|---|---|
| **误杀率 =(hitA-hitB)/hitA** | **5/742 = 0.67%** | **1/86 = 1.16%** | **4/656 = 0.61%** |
| 门控判零率 | 18/4495 = 0.40% | 6/932 = 0.64% | 12/3563 = 0.34% |
| C 相对 A / 相对 B | +200 条 / +205 条（丢 0） | +44 / +45（丢 0） | +156 / +160（丢 0） |
| C 的误杀（相对 A） | 5/742 = 0.67%（与 B 同一批） | 1/86 | 4/656 |

A/B 命中集**仅 A 命中 5 条、仅 B 命中 0 条**（B 的输出必然是 A 的子集：同模板、门控只删结果）。

## 三、★ 5 条误杀实例与机制

| reaction_id | T(℃) | 收率 | 给出该产物的模板 | 判零原因串（原文） | 机制 |
|---|---|---|---|---|---|
| ord-28f060e4b960… | 缺(->100) | 70.0 | mitsunobu | 温度 100℃ 高于实测上限 70℃，降权 | 边界 0.0 |
| ord-914e8800d70d… | 缺(->100) | 20.0 | mitsunobu | 同上 | 边界 0.0 |
| ord-4d53d8db1d6f… | 缺(->100) | 87.0 | mitsunobu | 同上（+溶剂降权） | 边界 0.0 |
| ord-c529b7fec375… | 缺(->100) | 19.5 | mitsunobu | 同上 | 边界 0.0 |
| ord-136552549722… | **-30.0** | 76.0 | esterification | 温度 -30℃ 低于实测下限 0℃，降权 | 边界 0.0 |

- 这 5 条 A 的产物 = **记录产物本身**（canon 完全相同）【实测】，B 产物 0 条 -> 真误杀。18 条判零里 **13 条是"降权到 0.0"的边界效应**（mitsunobu 12 + esterification 1），只有 5 条真正超窗（negishi_insitu 150℃>80+30、heck -78℃、C_C_decarboxylation 0℃ 与 65℃、reductive_amination_ketone 250℃）—— **这 5 条真正超窗的，A 一条都没命中**。
- 窗口宽度【实测】：37 类中 29 类有温度窗口，中位宽 160 ℃；最窄 `oxadiazole_condensation [150,150]`、`tetrazole_synthesis [80,80]`（宽 0）、`mitsunobu [-5,70]`；8 类无温度数据 -> 直接放行。判零类型分布（B+C 累加）：mitsunobu 38、C_C_decarboxylation 16、reductive_amination_ketone 10、negishi_insitu 4、heck 4、cross_electrophile_coupling 4、esterification 2。

## 四、温度缺失缺省的敏感性【实测】

- 缺省 100 ℃（主口径）：S_notemp 误杀 4/656 = 0.61%，4 条**全是** mitsunobu 的 70+30 边界巧合。缺省 25 ℃ 室温（`--notemp-temp 25`）：S_notemp 误杀 **0/656 = 0.00%**（那 4 条全消失），S_all **1/742 = 0.13%**、判零反而**更多**（18 -> 33 条，多出来的都没碰到 A 的命中），S_temp 不变（1/86 = 1.16%，用的是记录真实温度）-> **唯一由"记录真实温度"造成的误杀只有 1 条**（-30 ℃ 的 esterification）。

## 五、失败分类计数（15000 行抽样，一类一个计数器）

fail_reactants_gt2（REACTANT>2）9711 (64.74%)｜fail_reactants_lt2（<2）720 (4.80%)｜dup_skipped 74 (0.49%)｜fail_product_missing 0｜fail_product_unparsable 0｜fail_no_reactant_smiles 0｜fail_reactant_unparsable 0｜**qualified 入评测集 4495 (29.97%)**｜**step 抛异常（A/B/C 三配置）0**。[附] qualified 中 CXSMILES 左侧片段数 != 2 有 1281 条 (28.5%)、两个 REACTANT 同分子 8 条。

- qualified 里温度缺失 **79.3%（3563/4495）** > 全表 71.5%；【推断】"恰好 2 个 REACTANT"的记录更多来自不带条件字段的专利/论文。`fail_reactants_gt2` 65% 说明：**2/3 的 ORD 记录进不了"单一底物对"口径**（碱/硼酸/叠氮被标成 REACTANT），这是后续放开口径的方向。

## 六、抽样与检出功效

| 抽样 | qualified | A 命中 | B 命中 | 误杀 | 误杀率 |
|---|---|---|---|---|---|
| `--limit 3000` | 891 | 171 | 171 | 0 | 0.00%（未检出） |
| `--limit 15000` | 4495 | 742 | 737 | 5 | **0.67%** |

**3000 行的 0.00% 是功效不足**（按 0.67% 的真实速率，3000 行的 171 条命中期望只有 ~1.2 条误杀）-> 交付 JSON 用 15000 行（同一脚本、同一 seed，只是抽更多）；3000 行结果一并列出。`--limit 50` 冒烟：覆盖 42/178 片、qualified 15 条【实测】，用于验证管线。

## 七、坑与限制

1. **容差边界 = 隐式判零**（本轮最关键）：写的是"降权"，但衰减到边界正好 0.0，`step()` 的 `act <= 0.0` 就删了 —— 是【实测】的边界行为，不是化学判断。**缺温度 -> 任一缺省温度都会制造误杀**（§四）；【推断】正确做法是"温度缺失时门控不判零（放行）"，而不是拿假设温度去比窗口。
2. **试剂门控误杀仍空白**（REAGENT 可得率 0%）：Suzuki/Mitsunobu/酰胺缩合的"缺试剂判零"本次不触发。
3. **命中口径是精确 canon SMILES（含立体）**：放宽到去立体/InChIKey 前 14 位只会让 A/B 命中集都变大；5 条误杀是精确命中且 B 产物为 0，故分子仍 ≥5 而分母变大 -> **0.67% 是保守（偏大）估计**【推断】。
4. `reactants_n`（CXSMILES 左侧片段数）≠ REACTANT 角色数：qualified 里 1281 条（28.5%）不等，口径只能用角色数。命中率随收率升高而下降（结论 6）——按收率筛样本会给召回评估带来偏差。
5. `D:\TCMAI` 与 `ord-data\` 全只读；未改 `core\*`、`tools\hte_*.py`、`tools\ord_condition_dataset.py`、`tools\measure_*.py`、`tools\verify_*.py`、接手总结。

## 八、复现命令（seed 固定）

```powershell
cd D:\ProgramData\DSHNS\chemreact-staging
D:\TCMAI\venv\Scripts\python.exe tools\ord_gate_falsenegative.py --limit 50                    # 冒烟
D:\TCMAI\venv\Scripts\python.exe tools\ord_gate_falsenegative.py --limit 3000 --seed 20261013  # 任务要求（未检出）
D:\TCMAI\venv\Scripts\python.exe tools\ord_gate_falsenegative.py --limit 15000 --seed 20261013 # ★ 主结果=交付 JSON
D:\TCMAI\venv\Scripts\python.exe tools\ord_gate_falsenegative.py --limit 15000 --seed 20261013 --notemp-temp 25
```

产物：`tools\ord_gate_falsenegative.py`、`reports\ord_gate_falsenegative.json`、本报告。
