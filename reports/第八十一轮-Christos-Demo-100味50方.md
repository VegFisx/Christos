# 第八十一轮 · Christos-Demo 100 味 / 50 方

日期：2026-10-18

## 一、内容

Demo 从静态卡片升级为可选目录和预计算结果：

- **100 味常见中药**；
- 每味药选 **1 个拉丁物种**（`herb_species.json` 的首个物种）；
- **50 个方剂**，限 4–6 味，过滤掉高风险/受控相关条目；
- **150 个预计算条目**：100 味中药 + 50 个方剂，0 失败；
- 支持目录内查找、选择条目、点击“生成示例结果”。

结果口径：

- 每味中药：1 个物种成分、1 轮、水提、最多 5 条去重产物；
- 每个方剂：为控制演示体积，预计算只看前两味已映射药材，页面会明确标注；
- 结果只作流程展示，不是完整方剂预测、不是医学或合成结论。

## 二、数据边界

演示目录是从本地项目数据筛选出的**小型摘录**，不是完整数据库。

- 不包含 `tcm.db` / `coconut.db` / `formula_db.json`；
- 不包含任意目标 SMILES 输入；
- 不包含逆合成 routes；
- 不包含自由辅助试剂、可购砌块、供应商链接；
- 目录摘录只供约定测试者查看，不作为数据源再分发。

## 三、验证

目录合并结果：

```text
items=150
herbs=100
formulas=50
failures=0
```

打包版实测：

```text
HTTP 200
herbs=100
formulas=50
predictions=150
```

最终 ZIP 解压后再次启动，同样为 `HTTP 200`，目录数量一致；双击 Edge app 模式也已验证。

## 四、发布件

文件：

`reports\desktop-build\demo-v090\Christos-Demo-0.9.0-beta-demo.zip`

- 大小约 8.2 MB
- 60 个归档文件
- SHA-256：`6c6e02e1f2b5eaebdc643875e34b5c45a64bb5ee8df21262e1532f42ea26cc7e`

病毒扫描（Kaspersky，只报告模式）：

```text
Processed objects: 400
Total detected: 0
Suspicions: 0
Errors: 0
```

报告：`reports\desktop-build\demo-v090\KASPERSKY_SCAN_REPORT.txt`

## 五、白屏修复

有测试窗口出现空白页；服务端和页面资源实测均正常。定位为 Edge app 的 GPU/旧专用配置问题。
启动器已改为：

- 使用新的专用 `edge-profile-v2`；
- 启动 Edge app 时加 `--disable-gpu`；
- 页面仍只绑定 `127.0.0.1`。

修复后用独立 Edge app 实测页面标题 `Christos Demo · Catalog`，HTTP 200。

## 六、边界

这是可玩性更好的**预计算演示**，不是完整实时引擎。若测试者需要输入任意目标或真实方剂，需要另做受控研究版，继续遵守公开版禁用 routes、自由试剂和可购砌块的安全边界。
