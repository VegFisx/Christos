# -*- coding: utf-8 -*-
# One-shot: fifth-round fixes for the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

EDITS = [
    ("精确中文名和别名每次都解析成功，两组各有一个歧义结果。炮制品五个中成功三个：炒白术和姜半夏不在库里，返回的是炮制品闸的明确“库缺”，而不是被拆成基原。",
     "精确中文名和别名基本每次都解析成功，两组各有一个歧义结果。炮制品十个中只成功三个，其余七个（包括炒白术和姜半夏）不在库里，返回的是炮制品闸的明确“库缺”，而不是被拆成基原。"),
    ("四个本不该解析的字符串里，三个返回空。「甘」这个单字返回了 40 个候选，正好撞上子串匹配的上限，因为它能匹配到很多药名。",
     "十个本不该解析的字符串里，九个返回空。「甘」这个单字返回了 40 个候选，正好撞上子串匹配的上限，因为它能匹配到很多药名。"),
    ("### 逆合成与多步规划",
     "\n".join([
         "### 实验配置",
         "",
         "| 实验 | 目标集 | 模板库 | 产物级排除 | 可与谁比较 |",
         "|---|---|---|---|---|",
         "| 正向，基线 | 50,016 USPTO-50k | 引擎默认 | 是，对 USPTO-50k | 正向选定 |",
         "| 正向，选定 | 50,016 USPTO-50k | 约 2 万条 support 过滤 | 是，对 USPTO-50k | 正向基线 |",
         "| 逆向，子集 | 5,002 ORD | 79,184 | 是，另做目标重叠检验 | 无 |",
         "| 逆向，全量 | 50,016 USPTO-50k | 3,065 | 是 | 无 |",
         "| 多步 | 300 ORD | 选定库 | 未做目标重叠检验 | 无 |",
         "| 条件审计 | 500 条模板 | 生产库 | 不适用 | 无 |",
         "",
         "正向两组共用同一目标集，只差配置，所以可以比较。逆向两组既换目标集又换库，并列只为完整。多步沿用选定库，但没有做目标级重叠检验。",
         "",
         "### 逆合成与多步规划",
     ])),
    ("采用 beam width 4 和选定模板库时，端到端成功率在 300 个固定目标上为：",
     "\n".join([
         "5,002 个逆向目标做过一次与模板挖掘源的重叠检验。其中 252 个（5.04%）的产物也出现在该源里，",
         "这 252 个的 any-hit 是 94.84%（239/252）；其余 4,750 个没有重叠，达到 94.74%（4,500/4,750）。",
         "把重叠目标去掉，覆盖率在小数点后两位不变。",
         "",
         "300 个多步目标没有做同样的检验，成功率按实测报告，应理解为未做目标级过滤。",
         "",
         "采用 beam width 4 和选定模板库时，端到端成功率在 300 个固定目标上为：",
     ])),
]


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(EDITS, 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
