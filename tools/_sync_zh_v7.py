# -*- coding: utf-8 -*-
# One-shot: bring the Chinese draft up to the current English structure.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

OLD_TITLE = "# Christos：面向天然产物与中医药研究的可溯源、只读反应预测系统"
NEW_TITLE = "# Christos：面向药材与天然产物数据的可溯源、只读反应预测引擎（含显式输入解析）"

ABSTRACT_OLD = "500 条模板条件审计中，493 条至少有一次产物匹配，491 条至少有一类条件记录。"
ABSTRACT_NEW = (ABSTRACT_OLD +
                "五条有文献记载的中药转化，涵盖糖苷水解与酯水解，全部在第一轮可达。"
                "\n\n预测性能只在 USPTO-50k 和 ORD 上评估。中药部分按输入解析与出处层评估，"
                "不是反应预测基准：没有 TCM 反应 ground truth，573 条甘草台账也尚未对照实验或文献。")

KNOWN = "\n".join([
    "### 已知转化验证",
    "",
    "选取五条中药文献中有记载的转化做定性可达性检验。每条底物单独在煎煮条件下跑到三轮，"
    "然后在前台账里查找文献给出的产物。",
    "",
    "| 转化 | 规则 | 轮次 | 候选数 | 耗时 |",
    "|---|---|---:|---:|---:|",
    "| 甘草酸 → 甘草次酸 | hydrolysis_glycoside_001 | 1 | 5,510 | 56 s |",
    "| 人参皂苷 Rb1 → Rg3 | hydrolysis_glycoside_001 | 1 | 11,658 | 193 s |",
    "| 乌头碱 → 苯甲酰乌头原碱 | hydrolysis_ester_001 | 1 | 642 | 6 s |",
    "| 苯甲酰乌头原碱 → 乌头原碱 | hydrolysis_ester_001 | 1 | 814 | 7 s |",
    "| 芦丁 → 槲皮素 | hydrolysis_glycoside_001 | 1 | 5,685 | 96 s |",
    "",
    "五条产物全部在第一轮出现，而且都由化学上预期的规则产生：糖苷类走糖苷水解，"
    "两个二萜生物碱走酯水解。这说明管线能够抵达文献记载的煎煮化学，但不等于能把正确产物"
    "排到前面——系统根本不排序。",
    "",
    "乌头碱这两级在附子炮制文献里有记载（PubMed 27761113、18306748）。其余三条转化的"
    "具体文献尚未补齐，它们同样出自煎煮化学文献，只是本稿还没有一一对应到具体论文。",
    "",
])

FILTER = "\n".join([
    "### 两级筛选",
    "",
    "四君子汤那 3,210 条候选分两步压缩。第一步只保留中药规则库里的规则，去掉从 ORD "
    "挖来的通用有机合成模板，3,210 降到 1,114。第二步把每个产物的 InChIKey 拿去和"
    "药材库里的 31,646 个成分比对，6 个是已知中药成分，1,108 个不在库里。",
    "",
    "这 6 个已知成分来自四次酯水解和两次糖苷水解。整体压缩率 99.8%。读者拿到的不是"
    "3,210 个结构，而是 6 个有文献身份的具体化合物。",
    "",
    "这套筛选不是排序，也不带任何置信分。它只应用两条显式判据——规则来源和是否在成分表里——"
    "产物要么同时满足，要么不满足。库外那 1,108 个产物在另一个开关下仍然可取，它们是"
    "候选新成分，不是错误。",
    "",
])

APPS = "\n".join([
    "## 应用场景",
    "",
    "**方剂煎煮产物预测。** 给一组药材，返回只在合煎后出现的产物。四君子汤标准四味在筛选后"
    "给出 6 个有文献身份的成分。",
    "",
    "**炮制减毒机制。** 乌头碱经苯甲酰乌头原碱到乌头原碱的两级水解在第一轮就被复现。"
    "这正是附子、川乌、草乌炮制减毒的核心化学。",
    "",
    "**质量标准标志物筛选。** 煎煮后出现、原药材里没有的产物，可以作为区分汤剂与原生药粉的候选标志物。",
    "",
    "**配伍化学基础。** 两个前体分别来自不同药材的产物，是「这一组合、而非单味药产生了它」的直接证据。",
    "",
    "## 展望",
    "",
    "中药规则库现在有 64 条，系统性的文献挖掘可以把它做到几百条，这是覆盖面上最大的杠杆。"
    "筛选层目前只用规则来源和成分身份，加上质量守恒、条件窗口和文献先验会更紧。"
    "本文所有预测都还没有对照实验，那是把「可达性检验」变成「准确性结论」的关键一步。",
    "",
])

ANCHOR1 = "### 中医药案例"
ANCHOR2 = "## 讨论"
ANCHOR3 = "## 局限"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate([
        (OLD_TITLE, NEW_TITLE),
        (ABSTRACT_OLD, ABSTRACT_NEW),
    ], 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        s = s.replace(old, new, 1)
    print("anchor1=%d anchor2=%d anchor3=%d"
          % (s.count(ANCHOR1), s.count(ANCHOR2), s.count(ANCHOR3)))
    s = s.replace(ANCHOR1, KNOWN + ANCHOR1, 1)
    s = s.replace(ANCHOR2, FILTER + ANCHOR2, 1)
    s = s.replace(ANCHOR3, APPS + ANCHOR3, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
