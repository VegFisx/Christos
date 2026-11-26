# 第 219 轮：ORD 执行证据与 secondary 升级

> 证据层第二轮：不再只看「ORD 里有没有同款模板」，而是把规则逐条套到
> ORD 的真实反应上，看它能不能生成记录里的真实产物。
> 有强证据的规则升级为 `secondary`（数据证据），仍是 unvalidated 的不动。

## 1 做法

`tools/audit_rules_against_ord_reactions.py`

- 数据：`data/ord_reaction_index.jsonl`（177 万条 ORD 反应记录）；
- 抽样：等距 12 万条（stride 14），扫描 119,993 条，用时 1,763 s；
- 规则：73 条 active unvalidated；
- 判定：规则的底物模板先做子结构预筛，命中后正向跑反应，
  生成的产物规范化（去映射/去显式 H/去立体）后与记录产物比对；
- 计数：`fired` = 规则在记录上成功触发；`product_match` = 生成产物与
  记录产物一致。

## 2 结果

| 指标 | 数量 |
|---|---:|
| 至少 fired | **66 / 73** |
| 至少 product_match | **56 / 73** |
| 强证据（match ≥ 10 且 fired ≥ 20） | **41** |
| 弱证据（match 1–9） | 15 |
| 无命中 | 17 |

命中率差异很大，如实记录：

- 高：Suzuki 79%（920/1160）、Sonogashira 75%（287/381）、
  亚硫酰氯族 58%（307/525）、酰胺缩合 34%（6006/17414）；
- 低：芳环羟化 0.03%（35/109923）、烯烃水合 0.4%（70/15883）。

低命中率不等于规则错，但说明这些规则很宽；`secondary` 只表示
「这条变换在 ORD 里真实发生过并生成了记录产物」，不表示高选择性。

## 3 升级

`tools/promote_ord_evidence.py`：只改 `provenance`，不动 SMARTS /
副产物 / 状态 / 支持度。

- 41 条强证据规则：`unvalidated` -> **`secondary`**；
- 语义 diff 已核对：41 条规则**只有 `provenance` 一个字段变化**。

升级后：

| provenance | 数量 |
|---|---:|
| cited | 38 |
| **secondary** | **41** |
| unvalidated（active） | 32 |
| unvalidated（disabled） | 6 |

带证据规则共 **79 条**（cited 38 + secondary 41），其中 6 条 cited 仅用于炮制，
不计入默认文件级加载；**默认加载 32 -> 73 条**，探索档 105 条
（非 paozhi_only 的 active 规则）。

## 4 测试

- `test_reaction_cases.py`：**121/121**，覆盖 111/111；
- `test_provenance_gate.py`：PASS。
  - 修了一个测试脆弱点：它原来写死 `hydroxylation_aromatic_001` 作为
    「显式点名 unvalidated」的样本；这条规则本轮升级成 secondary 后，
    测试假失败。改成从当前 unvalidated 列表动态取第一条。
- 发布闸门 `release-9549463-20261124-2230.json`（quick，dirty 0）：**pass**。
  safety ERROR 0；smoke 45/45/49/45/83/45/45/**824** 与上版逐项相同；
  holdout 23/31；forward 0.8659；official 0.91 / 0.4167；
  rerank 0.93 / 0.7567 / 0.9167；multistep 0.56。
  **升级没有改变任何已发布基准。**

## 5 边界（必须写清）

1. **ORD 是通用有机反应数据，不是中药数据。** 它证明反应可行，
   不证明某味药在煎煮/炮制中真的走这条路径。
2. **`secondary` ≠ 文献证据。** 本轮没有新增文献引用；notes 里可核对
   DOI 仍是 8 条。
3. 抽样 12 万/177 万（6.8%），`product_match` 是**记录数**不是专利数；
   同一专利的大量实例会抬高计数。
4. 17 条无命中里，有一部分是中药特有反应（如苷类水解、Maillard），
   ORD 覆盖不到；这些需要文献或中药实验数据，不能靠加大抽样解决。

## 6 产物

- `reports/rule_ord_execution_20261124.{json,md}`
- `reports/rule_evidence_combined_20261124.{json,md}`
- `tools/build_rule_evidence_report.py`、`tools/promote_ord_evidence.py`
- 规则：117 条 / active 111 / cited 38 / **secondary 41** / unvalidated 32+6
