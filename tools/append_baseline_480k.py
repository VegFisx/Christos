"""把 480K 外部基线数字追加到论文口径文档（UTF-8 安全追加）。"""
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "reports" / "paper" / "基准口径-2026-11-04.md"
BLOCK = """
## 第七节 宽空间基线：USPTO-MIT 480K（2026-11-06，第一百一十八轮）

同一语料（`USPTO_MIT.csv`，479,035 行）确定性抽样 8.36%（md5，seed 20261106）→ **39,176 条**，
默认配置、煎煮、1 轮、立体默认开：

| 指标 | 数值 |
|---|---|
| 候选召回 | **71.18%**（平均候选 20.1） |
| top-1 | **32.81%** |
| top-3 / top-5 / top-10 | 45.80% / 51.89% / 61.68% |
| MRR | 0.4187 |

同语料文献 top-1：Molecular Transformer **90.4%**（`10.1021/acscentsci.9b00576`）、
Augmented Transformer 90.6%（`10.1038/s41467-020-19266-y`）、Chemformer 92.5%（`10.1088/2632-2153/ac3ffb`）、
Graph2SMILES 90.3%（`10.1021/acs.jcim.2c00321`）。

**写法纪律**：
1. 50K 上的 91.71% 是**候选召回**，不能与文献的 top-1 并排，也不能说「我们比 90.4% 高」。
2. 480K 上我们 top-1 只有 32.81%，比文献低约 58 pp —— 这是**覆盖差距**，必须写进 Limitation。
3. 三个不可比因素必须同时声明：切分不同（我们的哈希抽样 vs Jin 2017 固定 40k）、输入不同（我们不用试剂）、指标不同（召回 vs top-1）。
4. 严格同反应重叠 **0/479,035**（`tools/check_mit_overlap.py`），所以「背语料」的质疑在 480K 上同样不成立。

原始 53.8 MB 语料不入库（`.gitignore`），来源 URL 与校验见 `reports/第一百一十八轮-480K外部基线-20261106.md`。
"""


def main() -> int:
    if not DOC.exists():
        print("缺文件:", DOC)
        return 1
    text = DOC.read_text(encoding="utf-8")
    if "USPTO-MIT 480K（2026-11-06" in text:
        print("已存在第七节，跳过")
        return 0
    DOC.write_text(text.rstrip() + "\n" + BLOCK, encoding="utf-8")
    print("已追加第七节 →", DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
