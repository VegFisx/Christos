# 第七十五轮 · H3：验收用例改成「从 tcm.db 取」（前后对照）

> 任务书：`reports\第七十五轮-任务-数据出处隐患.md` 的 H3。
> 一句话：**用例里的分子不再手写** —— 能查到的改成 **InChIKey 引用**（运行时只读取 SMILES），
> 查不到的如实留字面量并标明原因；**回归前后逐条完全一致**。

---

## 一、动手前的基线（护栏①）

```powershell
python tools\test_reaction_cases.py  > reports\第七十五轮-用例DB化-基线-反应级.txt
python tools\db_cases.py             > reports\第七十五轮-用例DB化-基线-真实底物.txt
python tools\git_snapshot.py "H3 动手前快照：66/0 基线，用例仍是手写 SMILES"
```

| 基线 | 结果 |
|---|---|
| 反应级验收（66 条：61 rule + 5 gating） | **66 通过 / 0 失败** |
| 真实底物用例（db_cases.py，5 条） | **5 通过 / 0 失败** |
| 代码快照 | 见 `tools\git_snapshot.py` 的提交（本机无系统 git，仓库是 dulwich 建的，格式仍是标准 git） |

> 注：PowerShell 的 `>` 重定向写的是 **UTF-16LE**，读取它的脚本（`tools\compare_case_runs.py`）
> 已按 BOM 嗅探编码，不会读成乱码。

---

## 二、做法

1. **引用格式**（`tools\reaction_cases*.json`）：

   ```json
   "smiles": {"db": "QPJVMBTYPHYUOC-UHFFFAOYSA-N", "name": "Benzonic acid methyl ester"}
   "expect_any": [{"db": "WPYMKLBDIGXBTP-UHFFFAOYSA-N", "name": "Benzoic acid"}]
   "forbid":     [{"lit": "CC1CO1", "why": "库外（教科书级小分子 / 引擎产物；tcm.db 里没有）"}]
   ```

   引用是 **InChIKey**（分子的标准标识符，即库里 `compounds.inchi_key` 那一列），
   不是"我抄的 SMILES"。库里**查不到就报错**，绝不静默退回字面量。

2. **解析层** `tools\case_db.py`：用 `tools\tcm_ro.py` 的**只读**连接
   （`file:...?mode=ro`，打不开才回退 `immutable=1`）把 InChIKey 换成 SMILES。

3. **转换脚本** `tools\build_cases_from_db.py`：逐条把旧的手写值换成引用 ——
   只有当"库里那一行"与"原来手写的那个分子"**规范 SMILES 相等**时才替换，
   替换不了一律留字面量并在 `data\case_sources.json` 里逐条列出。

4. **归档（不删产物）**：旧文件原样进 `reports\第七十五轮-用例DB化-存档\` ——
   `reaction_cases.json`、`reaction_cases2.json`、`cases.py`、`cases2.py`（复制），
   `patch_cases.py`、`patch_cases2.py`、`patch_cases3.py`（历史补丁脚本，它们改的正是被替换掉的那版
   `cases.py`，已失效 → 移进存档）。**一个字节都没丢**。

---

## 三、改后结果（护栏②）

```powershell
python tools\test_reaction_cases.py            # 66 通过 / 0 失败（与基线一致）
python tools\db_cases.py                       # 5 通过 / 0 失败
python tools\compare_case_runs.py reports\第七十五轮-用例DB化-基线-反应级.txt reports\第七十五轮-用例DB化-改后-反应级.txt
python tools\verify_case_conversion.py         # 逐条核对"没偷换分子"
python tools\audit_handwritten_data.py         # 验收用例类的手写计数
```

**逐条一致性（实测）**：

```
  基线 67 条 ｜ 改后 67 条
  通过：基线 67 ｜ 改后 67
  ✓ 所有同名用例的通过/失败**完全一致**（0 处翻转）
```

**"没偷换分子"核对（实测）**：

```
  核对分子字段：数据库引用 86 处 ｜ 库外字面量 43 处（逐字相同）｜ 跳过 0 处
  ✓ 全部一致：引用取出来的分子与原来手写的**是同一张结构**（无一处偷换）
```

**审计计数（★验收用例★ 类）**：

| | 改前 | 改后 |
|---|---|---|
| 文件数 / 处数 | 11 个文件 / **287 处** | 7 个文件 / **91 处** |
| 其中：真·SMILES 字面量 | 129 处（分子字段） | **43 处**（全是库外的教科书小分子 / 引擎产物，逐条列在 `data\case_sources.json`） |
| 其中：数据库引用（InChIKey） | 0 | **86 处**（单列计数，不再混进"手写"里） |
| 其中：正则假阳性 | ~30 处（名字、模块路径，如 `Acetamide`、`rdApp.warning`） | ~40 处（同类，未动检测口径之外的东西） |

> 审计脚本本轮只加了一条**辨识规则**：`^[A-Z]{14}-[A-Z]{10}-[A-Z]$` 形状的字符串是
> **InChIKey 标识符**，不是 SMILES，单列计数（改前那 86 处引用一个也不"藏"，
> 全在报告里点名）。检测 SMILES 的其余口径**一字未改**。

---

## 四、本轮的坑（都比结论值钱）

1. ★ **同一个 InChIKey 在库里有多行不同写法**。苯酚 `ISWSIDIOOBJBQZ-UHFFFAOYSA-N`
   有 3 行，**第一行是离子写法** `[H+].C1=CC=C(C=C1)[O-]`（名字还叫「Iph」）——
   我第一版按 key 取"第一行"，等于把底物偷偷换成苯酚阴离子，
   回归当场挂 2 条（`ox_aromatic_hydroxyl`、`eli_demethylation`）。
   改成**优先取电中性的那一行**（全带电才用，并打警告）后 66/0 复原。
   —— 这正是"改前存基线、逐条比对"能抓到的东西。
2. **PowerShell `>` 写 UTF-16LE**：第一版对比脚本读出来 0 条用例，
   差点得出"基线为空、逐条一致"的假绿。现在按 BOM 嗅探编码。
3. **审计的正则是"像 SMILES"而不是"是 SMILES"**：`Acetamide`、`Glycyrrhizin`、
   `rdApp.warning` 这类名字/路径一直被计进"手写分子"（改前改后都在）。
   本轮没有扩大改动面去修它，只在报告里点名；真要修就是"用 RDKit 解析成功才算 SMILES"。

---

## 五、边界

* **引擎代码一行未改**（`core/`、`rules/`、`conditions/` 未动）—— 本轮只动用例数据、
  用例读取方式与审计脚本；所以回归范围就是两套用例（66 + 5 条），
  其余实测数字（召回/覆盖率）不受影响。
* `db_cases.py`（本身就是"底物按名字从 tcm.db 取"的那套）**未改**，它的 13 处计数是
  正则假阳性（库名、路径、化合物英文名）。
* **没有**放宽任何断言：期望产物一个都没删、没改判据；`want`/`forbid` 语义原样。
* `D:\TCMAI` 全程只读（`mode=ro`）；产出只落 `chemreact-staging\data\`、`reports\`、`tools\`。
