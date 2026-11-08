# Christos（炼膏师）V1.0.0 · 发布说明

> 产品名：**Christos（炼膏师）**；内部包名/命令仍为 `chemreact`。

**发布日期**：2026-10-15 ｜ **定义**：能支撑一篇 SCI 二区投稿的最小完备系统
（验收清单见 `reports/v1.0.0-验收清单（二区投稿就绪）.md`）。

## 能力与关键数字（细节与出处见 `论文-v1.0.0-主线与消融统计总表.md`）

* **正向（底物→产物）**：50k 单步召回 **82.32%**（泄漏剔除版，CI 81.98–82.65%）；
  两杠杆消融：旧默认 55.43% → 截断修复后 82.56%（泄漏版）；
* **逆向（目标→路线）**：单步覆盖率 **94.74%**（全量）/91.90%（freq10）；多步端到端
  **47.7%（depth≤2）/ 72.3%（depth≤3）**，n=300；
* **药典判据链（2025 版）**：覆盖 386/491 味；连接 3,277 行；gold 核对 93.5%
  （剔除已知缺陷 98.7%）；`--chp-priority` 开关默认关；
* **质量设施**：逆模板黑名单（83 条，默认关）、B6 确定性判据（默认开）、
  元素门预筛（默认开）、公平截断（默认关）、运行台账与 `history`。

## 安装与快速开始

```powershell
# 引擎目录（单一来源）：D:\ProgramData\DSHNS\chemreact-staging
# 桥接（TCMAI）：D:\TCMAI\chemreact
D:\TCMAI\venv\Scripts\python.exe chemreact.py info
D:\TCMAI\venv\Scripts\python.exe chemreact.py predict --herb 甘草 --limit 12 --rounds 1
D:\TCMAI\venv\Scripts\python.exe chemreact.py routes --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2
D:\TCMAI\venv\Scripts\python.exe chemreact.py history -n 20
# 网页版：双击 start_ui.bat
```

## 已知边界（同论文 Limitations）

无人工盲评；可用性判据含限时匹配；评测在 ORD 系数据内完成（已做泄漏剔除）；
条件层只标注不模拟；药典链依赖第三方结构化版本（21% 未连接：矿物/聚合/尾料）。

## 文件与完整性

* 发布包：`reports/release/chemreact-v1.0.0-pack.zip`（34 文件、16.6 MB，含 manifest）
* 哈希清单：`reports/release/sha256_manifest.txt`（36 条，关键库与结果全覆盖）
* 第三方组件注记：RDKit（BSD-3）；反应数据来源 ORD（社区标准，CC0/公开）；
  药典文本仅作内部研究引用、只提取事实并标出处。

## v1.1+ backlog（有意缓做）

试剂/条件感知生成 · 预筛 v2（mono 池）· 药典覆盖率 79→90% · AiZynthFinder 基线 ·
更深的 TCMAI 集成（launcher/落库）· 用户手册全文与补充截图。
