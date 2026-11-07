# 第四十四轮：把化学 AI 接进 TCMAI 项目（桥接包）

> 用户 2026-10-14 要求："把现在这个接到我的 TCMAI 项目来"。
> 原则：**只新建一个子目录，不动 TCMAI 任何现有文件**；读库只读；爬虫/VS Code/formula_db 一律不碰。

---

## 一、交付物

```
D:\TCMAI\chemreact\            （新目录；除此之外 TCMAI 一个文件没动）
├── chemreact.py               桥接入口（predict / routes / info 三个子命令；12.8 KB）
├── README.md                  用法 + 安全边界 + 副作用说明
├── .gitignore                 （out/ 不进 git）
└── out\                       输出（示例已生成：甘草 3 成分 1 轮台账）
```

桥接**不复制引擎代码**：运行时从 `D:\ProgramData\DSHNS\chemreact-staging` 直接加载
（单一来源；路径可用环境变量 `CHEMCREACT_STAGE` 覆盖）。

## 二、验证（都在 TCMAI 自己的 venv 3.12.6 下实测）

| 命令 | 结果 |
|---|---|
| `chemreact.py info` | 引擎目录 ✓ · 逆模板 3,025 条 · 黑名单 54 条（默认关）· tcm.db 只读 31,646 行 ✓ |
| `chemreact.py predict --herb 甘草 --limit 3 --rounds 1` | 48 产物 / 48 出处路径 / 2.1 s；方向层 24 可疑 + 24 未定；条件依据已标；台账 CSV+TSV+meta 写入 `out\` |
| `chemreact.py routes --target <阿司匹林> --pool-file ...\_pool_aspirin_demo.txt --depth 1` | 1 条路线、可用=True，路线报告写入 `out\` |

## 三、安全核查（实测）

* `tcm.db`：大小 63,127,552、修改时间 **2026/9/15** —— **未发生任何数据写入**。
* 只读打开的**边车副作用**（如实记录）：在有写权限环境里第一次只读连接 WAL 模式的库，
  SQLite 生成 `tcm.db-wal`（**0 字节**）与 `tcm.db-shm`（32 KB）—— WAL 正常机制，
  主库没变、wal 为空。按纪律**不删除**这两个文件（README 已写明；未来写入方会正常复用）。
* 输出全部落在 `D:\TCMAI\chemreact\out\`；`formula_db*`、VS Code、爬虫痕迹一概未触碰。
* 核查时尚无 python 进程在跑（爬虫可能处于间歇）；我们的运行没有驻留任何连接。

## 四、怎么用（给用户）

```powershell
cd D:\TCMAI\chemreact
D:\TCMAI\venv\Scripts\python.exe chemreact.py info
D:\TCMAI\venv\Scripts\python.exe chemreact.py predict --herb 甘草 --limit 12 --rounds 1
D:\TCMAI\venv\Scripts\python.exe chemreact.py routes --target "CC(=O)Oc1ccccc1C(=O)O" --depth 2
```

## 五、边界与后续

* 桥接遵守既有纪律：**只打标记、不打分、不排序**；查不到 ≠ 不存在。
* 条件层目前只做标注（煎煮等场景层按原计划最后补）。
* 若要更深集成（接进 `launcher.py` / `tcm_analyzer.py` 的菜单或按钮），等用户指定入口再动——
  本轮刻意没有改任何现有文件。
* 论文线（USPTO-50k 基准跑）暂停中：已完成覆盖率（any-hit 79.8% / top-50 65.8%）与
  抽样可用性（496,047 切断：可用 30.8%、R2 57.5%、R1 10.5%；黑名单后 32.3%）；
  剩余：不稳定性三轮实验、出图、标注页生成、收尾打包。
