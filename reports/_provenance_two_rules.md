# 第七十五轮 · 规则来源体检（ORD 真实反应实测）

> **做法**：把每条规则的 SMARTS 套到 ORD 真实记录的**反应物**上，生成产物经「去映射号 / 去显式 H / 去立体 / 拆片段」规范化，再与记录的真实产物比对。
> **product_match** = 生成片段与该记录真实产物有交集；**fired** = 规则至少生成过一个可解析产物。

## 口径（先看这段）

* 数据源：`D:\ProgramData\DSHNS\chemreact-staging\data\ord_reaction_index.jsonl`，共 1,770,980 行；按步长 29 等距抽样，实际扫描 **59,999** 条。
* 这是**前向试跑**，不是逆合成审计；ORD 记录未必是同一反应类型，所以 `fired` 多不代表规则对，只代表底物里存在可匹配子结构。
* 规则里的水/共试剂多为**隐含**（如水解规则不把 H2O 写成反应物），因此本审计只把规则套到记录的反应物列；这比方案 a 的模板签名更接近真实用法。
* 规范化忽略立体与显式 H；`product_match` 是**分子图相同**，不是条件/机理相同。
* 只给计数与样例，**不打分、不排序**；`rules.json` 原顺序。

## 总览

* 规则：**2** 条（{'论文修正': 1, '自写新增': 1}）
* 至少 `fired` 一次：**2** 条
* 至少 `product_match` 一次：**1** 条
* 反应物解析失败：**0** 次；产物解析失败：**0** 次

## 逐条结果

| # | 规则 | 类别 | 状态 | 论文档位 | fired | product_match | run_errors | 首个命中 rid |
|---|---|---|---|---|---|---|---|---|
| 1 | `reduction_quinone_001` 醌还原 | reduction | active | 论文修正 | 117 | 0 | 0 | — |
| 2 | `reduction_nitro_001` 硝基还原成胺 | reduction | disabled | 自写新增 | 5067 | 1034 | 0 | ord-67ec3bcdf85a4cd095b46cc07afa68ed |

## 命中样例（前 3 条）

### `reduction_nitro_001` 硝基还原成胺

* `ord-67ec3bcdf85a4cd095b46cc07afa68ed`
  * 反应物：`Cc1c([N+](=O)[O-])ccc2c1C(=O)NS2(=O)=O + [H][H]`
  * 生成命中：`Cc1c(N)ccc2c1C(=O)NS2(=O)=O`
  * 记录产物：`Cc1c(N)ccc2c1C(=O)NS2(=O)=O`
* `ord-68a8e77da56c464fb8e4488b01b277d1`
  * 反应物：`Cc1cc(C#N)ccc1[N+](=O)[O-] + O=C([O-])O.[Na+] + [Cl][Sn][Cl]`
  * 生成命中：`Cc1cc(C#N)ccc1N`
  * 记录产物：`Cc1cc(C#N)ccc1N`
* `ord-53a3ebdf15d441468909b1e846bdef45`
  * 反应物：`O=[N+]([O-])c1ccc(Cl)cc1[N+](=O)[O-] + [NH4+]`
  * 生成命中：`Nc1cc(Cl)ccc1[N+](=O)[O-]`
  * 记录产物：`Nc1cc(Cl)ccc1[N+](=O)[O-]`

## 失败/无命中说明

* 没有 `product_match` 的规则不等于“规则错”：可能是 ORD 抽样里没有该反应类型、底物取代基不匹配、规则要求多步/共试剂，或记录方向相反。
* `run_errors` 是 RDKit 在具体底物上抛错的次数，已逐条累计；`invalid_products` 是生成物无法规范化的次数。
* 需要外部权威规则来源时，下一步应查论文/数据集原文；本报告只回答“有没有在 ORD 真实记录里跑出相同产物”。
