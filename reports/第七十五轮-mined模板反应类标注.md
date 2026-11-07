# 第七十五轮 · mined 模板反应类标注（C）

> 已知类模板：`libs/smartreact/data/templates.txt`；mined：`reports/mined_forward_templates_full_lf.jsonl`。
> 高置信 = 反应中心签名唯一对应一个 reaction_name；多类同签名不猜，标 `ambiguous`；无同签名标 `none`。
> ★ **结论：37 类映射不可行**（10k 试点 exact=0）；已改用
> `reports\第七十五轮-mined模板条件窗口（TopN）.md` 的 per-template 条件窗口。

## 总览

* mined 模板：**10000** 条（解析失败 0）
* `exact`：**0** 条（support 权重 0.0%）
* `ambiguous`：0 条（support 0.0%）
* `none`：10000 条（support 100.0%）

## 已标注类的 support 分布（前 30）

| reaction_name | support 合计 |
|---|---:|

## 机器可读

`data/mined_template_classes.jsonl`
