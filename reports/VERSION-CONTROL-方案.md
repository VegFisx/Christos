# 版本控制方案：现状、发现、与三条可走的路

> 本文档解决目标里的「前置保障：先做 git 版本控制」。
>
> **★ 第 25 轮更新：这一条已经解决了 ★**
> 不用装系统 git、不用管理员权限、不用等批准——
> 纯 Python 的 git 实现（dulwich）已装入暂存区 `libs\`，
> 已验证能做 `init / add / commit / log / status / diff / checkout`，
> 生成的 `.git` 是**标准 git 格式**。
> 详见本文第 6 节「第三条路（推荐）」。

---

## 1. 现状体检

| 检查项 | 结果 |
|---|---|
| 系统 PATH 里有 git | ❌ 无 |
| `C:\Program Files` / `Program Files (x86)` / `LOCALAPPDATA\Programs` / `D:\` / scoop / chocolatey | ❌ 全盘没有 `git.exe` |
| DSH 自带 git | ❌ 无 |
| Python 的纯 git 实现（dulwich） | ✅ **已装（1.2.17，在暂存区 libs\）** |
| `D:\TCMAI\.git` | ❌ 不存在 |
| **暂存区 `.git`** | ✅ **已建（提交 `2ea9b325ac06`，357 文件）** |
| **`winget`** | ✅ 可用 |
| **`winget` 里的 git** | ✅ **`Git.Git 2.55.0.5` 可装** |


### 你现在用的是什么

`D:\TCMAI\backups\`（394 MB）里是**手工复制的文件**：

```
coconut_final.db                      295 MB
tcm_final.db                           63 MB
herb_aliases_map_20260921.json          0.9 MB   ← 文件名带日期，典型的手工快照
admet_cache/
```

**这是手工快照，不是版本控制。** 它的问题：

- 只管几个大文件，**`src/` 里的 14 个 Python 文件一个都没备份**
- 没有历史记录，看不出"谁在什么时候改了什么"
- 文件名带日期 = 每次都要手动起名、手动清理
- 改坏了没法精确回退到"改之前那一版"

---

## 2. 我本轮做了什么：不依赖 git 的保命网

既然 git 装不了，我先把**本质的保护**做掉——**源码快照 + 哈希校验 + 一键还原**。

### 已建立

```
D:\ProgramData\DSHNS\chemreact-staging\snapshots\
├── TCMAI-src-20261010-191318\      ← 快照（100 个文件，0.50 MB）
│   ├── src\          14 个 .py
│   ├── scripts\      40+ 个 .py
│   ├── docs\github_upload\...
│   ├── requirements.txt / launcher.py / TCMAI.spec / .gitignore
│   └── _MANIFEST.json               ← 每个文件的 SHA256
└── restore.py                      ← 还原脚本
```

**为什么只 0.5 MB**：只快照代码与配置。
数据库（345 MB）、venv（1.5 GB）、Miniconda 安装包（126 MB）不是代码，
而且它们**本轮全程只读，没被碰过**。

### 校验过：快照是完整可还原的

```
文件数  : 100
总大小  : 0.50 MB
✓ 全部 100 个文件哈希一致，快照完整可还原
```

### 还原脚本是「默认演练」的

```powershell
# 列出可用快照
python restore.py

# 演练：显示会改哪些文件，但【不写入】
python restore.py --snapshot TCMAI-src-20261010-191318

# 真还原（会先把当前状态另存一份，免得冲掉新改动）
python restore.py --snapshot TCMAI-src-20261010-191318 --apply
```

实测演练输出：

```
快照: ...\TCMAI-src-20261010-191318
文件数: 100
  一致 100 | 不同/缺失 0 | 快照自身缺文件 0

（演练模式，未写入任何文件）
```

> **默认不写入**是刻意的。参考第 6 轮的教训：一个会改数据的工具，
> 如果默认就动手，很容易把好东西改坏（那次推导器覆盖坏了美拉德简化）。

---

## 3. 三条路，你挑一条

### ★ 路线 0：纯 Python git（dulwich）——**已经做好了，不需要你点头** ★

**第 25 轮新增。这一条不需要装任何系统软件、不需要管理员权限、不影响任何全局配置。**

```powershell
pip install --target D:\ProgramData\DSHNS\chemreact-staging\libs dulwich
```

装完之后我就能直接对 `D:\TCMAI` 做完整版本控制：

```python
import sys; sys.path.insert(0, r"...\chemreact-staging\libs")
from dulwich import porcelain
porcelain.init(r"D:\TCMAI")                    # 建仓库
porcelain.add(r"D:\TCMAI")                     # 暂存
porcelain.commit(r"D:\TCMAI", message=b"...")  # 提交
```

已验证的能力（`tools\verify_git_capability.py`）：

| 操作 | 结果 |
|---|---|
| `.git/HEAD` 内容 | `ref: refs/heads/master` ← **标准 git 格式** |
| `init` / `add` / `commit` | ✓ |
| `log` | ✓ |
| `status` | ✓ |
| `diff` | ✓ 输出标准 unified diff |
| `checkout` 回滚 | ✓ |

**所以「先做 git 版本控制」这个前置保障，技术上已经不再是阻塞了。**
真正的阻塞只剩一条：**要不要写 `D:\TCMAI`**。

> 顺带：暂存区本身也已经入库了（提交 `2ea9b325ac06`，357 文件，2.72 MB）。
> 这 32 轮的产出此前完全没有版本控制。

### 路线 A：装系统 git（可选，更方便你日后自己用）

**装 git 是系统级改动**，比改你的项目代码影响更大，所以我不擅自动手。

```powershell
winget install --id Git.Git --exact --accept-package-agreements --accept-source-agreements
git --version          # 期望输出 git version 2.55.0.5
```

已确认：包在 winget 源里、版本 2.55.0.5、命令格式正确。

装完之后：
- dulwich 建的仓库**直接可用**（格式一致），不用重建
- 你日后自己 `git log` / `git diff` / 用 GUI 都会更方便

**这条不再是"必须"，而是"更方便"。**

装完我就能做完整流程：

```
1. 修正 .gitignore（现在这个有三个毛病，见下）
2. git init + 首次提交存档
3. 跑一次 git status 确认干净
4. 然后把 63 条规则 + 核心模块搬进项目
5. 跑完整回归对比（旧引擎 vs 新引擎）
```

**必须先修的 `.gitignore` 问题（已用模拟验证，不是估计）：**

现在 `D:\TCMAI\.gitignore` 的全部内容只有三行：

```
.env
venv/
_pycache_/          ← 拼错了，少一个下划线
```

我写了个模拟器（自己实现 gitignore 匹配规则，**不需要 git 也能算**）走了一遍项目：

| `.gitignore` | 会被提交 |
|---|---|
| **现状** | **526 个文件 / 822.7 MB** |
| 修正后 | 190 个文件 / 56.5 MB |

现状会提交进去的大件：

| 大小 | 文件 |
|---|---|
| 281.7 MB | `coconut.db` |
| 126.4 MB | `Miniconda3-latest-Windows-x86_64.exe` |
| 122.9 MB | `data\admet_cache.db` |
| 60.2 MB | `tcm.db` |
| 56.3 MB | `tools\xtb\...\bin\xtb.exe` |
| 51.9 MB | `data\admet_cache.pkl` |

而上面这个模拟**还跳过了** `venv/`（1.5 GB）、`archive/`（437 MB）、
`backups/`（395 MB）、`build/`、`dist/`——现行规则同样没排除它们，
**真算上总量约 3.2 GB**。第一次 `git add -A` 会卡住甚至出错。

### 路线 B：就用我这套快照（零安装）

不想装东西的话，快照 + 还原已经能覆盖**最重要的风险**——「代码改坏了要能退回去」。

```powershell
# 每次要动代码之前，先做一次快照（0.5 MB，1 秒）
# —— 这一步我可以在每次改造前自动帮你做
python restore.py                      # 看有哪些快照
python restore.py --snapshot <名字> --apply   # 退回去
```

**够用吗？** 对"改坏了能退回去"够用。
**不够的地方**：没有分支、没有 diff 视图、没法 `git blame` 看谁改的、
跟 GitHub 对接不了（你 `docs/github_upload/` 看起来是想推到 GitHub 的）。

### 路线 C：两条都要（我的建议）

- **快照**：马上就有，作为最后一道保险
- **git**：等你方便时装上，用于日常开发、diff、和将来推到 GitHub

两者不冲突：快照管"整体退回去"，git 管"精细的版本管理"。

---

## 4. 无论走哪条路，我接下来都会做的

1. **每次改 `D:\TCMAI` 之前自动做快照**（0.5 MB，代价可忽略）
2. **改完跑回归对比**：旧 `predict_reactions` vs 新引擎，差异清单给你看
3. 已经准备好的东西（61 条规则、三道校验闸门、条件层、级联、评分、追溯）
   整体搬进去，`src/` 里旧的对应部分保留不删，用开关切换

---

## 5. 一句话总结

| | |
|---|---|
| 目标里的「前置保障：git」 | **卡在"机器上没装 git"**，不是缺批准 |
| 我本轮补的 | 源码快照 + 哈希校验 + 一键还原（0.5 MB，已实测） |
| 需要你做的 | 二选一：① 允许我 `winget install Git.Git`；② 就用快照方案 |
| 我这边随时可做 | 快照、回归对比、搬文件——**只要你给一句话** |
