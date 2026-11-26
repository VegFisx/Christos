# 第一百八十轮：规则 provenance 变成真正闸门

> 用户选择第 2 项：`unvalidated` 规则只在探索模式开启，不进入
> evidence / 生产默认。规则文件未改；只改引擎、入口与验证。

## 1 问题

`rules/rules.json` 早就记录了每条规则的 `provenance`，但引擎只检查
`status=active`，**不检查 provenance**。实际盘点：

| 口径 | 数量 |
|---|---:|
| 规则总数 | 78 |
| active | 72 |
| disabled | 6 |
| provenance=`cited`（active） | 19 |
| provenance=`unvalidated`（active） | 53 |

也就是说，默认的文件级 curated 加载会把 53 条未标定规则当成正常规则使用；
`provenance` 只是台账里的一行字，没有进入加载决策。

## 2 闸门口径

- **validated = `cited` 或 `secondary`**。缺失 provenance 按 unvalidated 处理。
- **默认文件级加载**（`curated_rule_ids=None`、`allow_unvalidated=False`）：
  只加载 validated 规则；unvalidated 规则跳过，并把跳过数写进 `curated_note`。
- **探索模式**：`allow_unvalidated=True` 恢复全部 active 规则。
- **显式 `curated_rule_ids`**：调用方点名，视为探索入口；允许 unvalidated，
  但在 `curated_note` 里单独计数（`显式 unvalidated N`）。证据表与单规则测试
  都走这条路径，行为不变。
- `RunSpec` / `SmartReactEngine` 的默认 `allow_unvalidated=False`（严格）。
- **CLI 解析**：通用/煎煮是探索口径（默认 `True`），炮制 evidence/production
  是严格口径（默认 `False`）。`--strict-provenance` 强制严格，
  `--allow-unvalidated` 强制探索；两者互斥。

## 3 改了什么

| 文件 | 改动 |
|---|---|
| `core/smartreact_engine.py` | 新增 `allow_unvalidated`；`_load_curated_templates` 按 provenance 过滤并计数 |
| `core/query_base.py` | `RunSpec.allow_unvalidated` 字段；透传给引擎 |
| `integration/tcmai_bridge/chemreact.py` | CLI 解析：通用/煎煮探索、炮制严格；`--strict-provenance` / `--allow-unvalidated`；写进 `switches` 与 `RunSpec` |
| `tools/validate_literature_paths.py` | `general` 显式 `allow_unvalidated=True`（探索口径）；evidence/production 为 False |
| `tools/paper_bench_official_test.py` | `CHEMCREACT_BENCH_CLI_CONFIG`（历史 CLI 基准）显式允许 unvalidated，避免已发布基准被闸门改动 |
| `tools/test_provenance_gate.py` | 新增专用验证 |

## 4 验证

`tools/test_provenance_gate.py` **PASS 8/8**：

| 检查 | 结果 |
|---|---|
| 默认加载 | 13 条（19 cited − 6 paozhi_only） |
| 默认跳过 | 53 条 unvalidated |
| 探索模式 | 66 条（72 active − 6 paozhi_only） |
| 显式点名 unvalidated | 1 条，note 记 `显式 unvalidated 1` |
| 证据表 provenance | 18 条全部 cited/secondary，无缺失 |
| 证据表加载 | 18 条 |
| RunSpec 透传 | 苯甲醇默认 1 个产物，探索 6 个 |

同时：

- `test_reaction_cases.py` **82/82**，覆盖 **72/72**；
- `audit_rules_balance.py` **0 异常**；
- `audit_rules_structure.py` **ERROR 0**；
- `audit_mapped_safety.py` **ERROR 0**；
- `run_paozhi_smoke.py` 手工复核：7 个炮制场景与 `guard_jiandao`
  **45/45/49/45/83/45/45/824**，没有变化。

## 5 行为影响

- **evidence / production（炮制）**：证据表 18 条全部 cited/secondary，
  产物数与 holdout 不变。
- **general / 煎煮（CLI）**：明确当作探索口径，默认仍加载 66 条；
  `guard_jiandao` 保持 824。`--strict-provenance` 才降到 13 条 validated。
- **第一次闸门尝试的教训**：先按“通用也严格”实现时，`guard_jiandao`
  从 824 掉到 538（−35%），被 release gate 的 smoke 硬检查拦截；
  这不是可接受的回归，因此把通用/煎煮定为探索口径，只让
  evidence/production 严格。
- **显式规则测试**：不变；点名规则仍可加载，只是计数。
- 规则文件、规则状态、规则 SMARTS、证据表均未改。

## 6 Release gate quick

在提交 `306e620` 的干净树上、以 `release-ce547f6-20261122-2245.json`
为基线重跑：

| 项 | 结果 |
|---|---|
| rev / dirty | `306e620` / `0` |
| safety | ERROR 0（WARN 14，既有） |
| holdout | **23/31** consistent（25/31 prediction hits） |
| smoke | 45 / 45 / 49 / 45 / 83 / 45 / 45 / **824** |
| forward | n=5630，recall **0.8659** |
| official | n=300，recall **0.91**，top1 **0.4167** |
| official_rerank | n=300，recall **0.92**，top1 **0.75**，top5 **0.91** |
| multistep | n=50，rate **0.56** |
| verdict | **pass**（hard=[]，soft=[]） |

记录：`reports/benchmarks/release-306e620-20261122-2342.json`。

闸门结果说明 provenance 策略没有改变任何已验证数字：炮制 smoke、
`guard_jiandao` 824、holdout 31 例、forward/official/rerank/multistep
全部与上一份基线一致。通用/煎煮仍走探索口径；`--strict-provenance`
是显式收紧开关。

## 7 产出

- 代码：`core/smartreact_engine.py`、`core/query_base.py`、
  `integration/tcmai_bridge/chemreact.py`、`tools/validate_literature_paths.py`、
  `tools/paper_bench_official_test.py`。
- 验证：`tools/test_provenance_gate.py`。
- 文档：`REPRODUCE.md` 的 Rule provenance gate 节。
- 规则：未改（78 条，active 72，disabled 6；evidence 18 条）。
