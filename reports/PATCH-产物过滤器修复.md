# 补丁提案：产物过滤器误杀（`src/tcm_analyzer.py`）

> 这是**唯一**需要改动你现有代码的地方，所以单独写出来供你审阅。
> 我**没有动手**，等你点头。

---

## 问题回顾

`D:\TCMAI\src\tcm_analyzer.py` 第 274–285 行：

```python
def _valid_product(mol, min_mw=100, min_heavy=10) -> bool:
    try:
        flag = Chem.SanitizeMol(mol, catchErrors=True)
        if flag != Chem.SanitizeFlags.SANITIZE_NONE:
            return False
    except Exception:
        return False
    if Descriptors.MolWt(mol) < min_mw:
        return False
    if mol.GetNumHeavyAtoms() < min_heavy:      # ← 问题在这
        return False
    return True
```

`min_heavy=10` 的实测后果：

| 分子 | 重原子 | 分子量 | 结果 |
|---|---|---|---|
| 水 | 1 | 18 | ★丢弃★ |
| 甲醇 | 2 | 32 | ★丢弃★ |
| 二氧化碳 | 3 | 44 | ★丢弃★ |
| 乙酸 | 4 | 60 | ★丢弃★ |
| 苯酚 | 7 | 94 | ★丢弃★ |
| **苯甲酸** | **9** | **122** | **★丢弃★** |
| 苯甲酸甲酯 | 10 | 136 | 保留 |

**苯甲酸只差 1 个重原子就被删了。** 而它正是乌头碱「酯水解减毒」的标志性产物——

实测证据（用真实附子成分 `13,15-dideoxyaconitine` 跑酯水解）：

```
原代码保留 2 个：C27H43NO7 (MW 494) + C32H45NO7 (MW 556)
原代码丢弃 2 个：C7H6O2 (MW 122, 重原子 9)  ← 苯甲酸
                C2H4O2 (MW 60,  重原子 4)  ← 乙酸
```

**给中药学院的老师演示时，这一条一问就露馅。**

---

## 修法：不删数据，只做分类

「删掉不该删的」比「显示太多」危险得多——前者会**静默改变结论**。

```python
# 新增：小分子副产物的判定门槛（是【标记】不是【删除】）
BYPRODUCT_MAX_MW = 46.0      # 水 18、甲醇 32、CO2 44；甲酸 46 恰好在上界
BYPRODUCT_MAX_HEAVY = 2
DISCARD_MIN_MW = 2.0         # 低于此值根本不是分子（H+、单原子离子）


def classify_product(mol) -> tuple[bool, bool]:
    """返回 (是否保留, 是否小分子副产物)。

    只丢真正不是分子的东西；小分子一律保留但打标记，
    由上层决定是否折叠显示，而不是在这里静默删掉。
    """
    try:
        if Chem.SanitizeMol(Chem.Mol(mol), catchErrors=True) != Chem.SanitizeFlags.SANITIZE_NONE:
            return False, False          # 价态非法 = 真正的坏数据
    except Exception:
        return False, False

    mw = Descriptors.MolWt(mol)
    heavy = mol.GetNumHeavyAtoms()
    if mw < DISCARD_MIN_MW or heavy < 1:
        return False, False

    is_byproduct = (mw <= BYPRODUCT_MAX_MW) or (heavy <= BYPRODUCT_MAX_HEAVY)
    return True, is_byproduct
```

### 最小改动版（如果你只想动一行）

如果你暂时不想动结构，**最低限度**也要把阈值放下来：

```python
# 第 274 行
- def _valid_product(mol, min_mw=100, min_heavy=10) -> bool:
+ def _valid_product(mol, min_mw=30, min_heavy=3) -> bool:
```

这样苯甲酸（9 重原子）、乙酸（4）、苯酚（7）都能保住，
只有水和甲醇（2 个重原子以下）会被挡掉。
**但这仍然是"删数据"思路，不如上面的分类法干净。**

---

## 已经验证过的替代实现

我在暂存区把上面这套写成了可运行的代码，并用真实数据验证：

- `chemreact-staging/core/engine.py` 的 `classify_product()`
- 实测：**19/19 项检查通过**（`reports/test_e2e.txt`）

端到端证据（用真实苯甲酸酯底物）：

```
底物：苯甲酸甲酯 COC(=O)c1ccccc1   规则：酯水解
产出 2 个产物：
    CH4O       MW    32.0  重原子  2 [副产物]
    C7H6O2     MW   122.1  重原子  9  ★苯甲酸★

底物：13,15-dideoxyaconitine（真实附子乌头碱）  规则：酯水解
产出 4 个产物：
    C2H4O2     MW    60.0              ← 乙酸
    C32H45NO7  MW   555.7
    C27H43NO7  MW   493.6
    C7H6O2     MW   122.1  ★苯甲酸★
```

---

## 附带效果：酸水解条件下减毒产物自动排到最前

接上新引擎后，`酸水解` 条件下的 Top 5 **全部**是酯水解产物：

```
【酸水解】water / 100°C / 120min / pH 1.5 / air / 催化:acid
  Top 5：
    0.910  C18H32O2    酯水解  ← Lipoaconitine
    0.910  C7H6O2      酯水解  ← Lipoaconitine     ← 苯甲酸
    0.910  C8H8O3      酯水解  ← Liwaconitine
    0.910  C2H4O2      酯水解  ← Pseudaconitine    ← 乙酸
    0.910  C9H10O4     酯水解  ← Pseudaconitine
```

而 `煎煮` 条件下 Top 5 是氧化/脱水类。
**「换个工艺，产物排序就变了」——这才是这个项目真正的卖点。**

---

## 要不要我动手？

| 选项 | 说明 |
|---|---|
| **A. 我直接改** | 改 `src/tcm_analyzer.py` 一个文件，改完跑回归对比（旧阈值 vs 新分类），给你看差异清单 |
| **B. 只出 patch 文件** | 我生成 `.patch`，你自己 `git apply`（但前提是先 `git init`） |
| **C. 先不动** | 保持现状，等新引擎整体切换时一起换掉 |

我的建议是 **C**：反正新引擎已经跑通且验证过，
没必要在旧代码上打补丁、再迁移一次。
等 `chemreact/` 整体进项目时，旧 `predict_reactions` 自然被替换掉。
