# -*- coding: utf-8 -*-
# One-shot: bring the Chinese manuscript in line with the English v3 edits.
# Each replacement reports a hit count so a missed anchor is visible.
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
    # 1. abstract: two reverse coverage figures
    ("逆向模板搜索在 5,002 个目标上达到 **94.74%** 的 any-hit 覆盖率；",
     "逆向模板搜索在 5,002 个目标的子集上、配 79,184 条模板的库达到 **94.74%** 的 any-hit 覆盖率，"
     "在全量 50,016 个目标上、配 3,065 条泄漏剔除库则为 **79.81%**；"),
    # 2. abstract: scalar field audit
    ("500 条模板条件审计中，493 条至少有一次产物匹配，491 条至少有一类条件记录。",
     "500 条模板条件审计中，493 条至少有一次产物匹配，491 条至少有一类条件记录。"
     "对一份 573 条记录的中药运行做字段级审计，九个出处处字段组全部出现，"
     "但条件理由是实质内容的只有 1.2%。"),
    # 3. results: reverse coverage + CIs
    ("泄漏受控逆向搜索在 5,002 个目标上达到 **94.74%** 的 any-hit 覆盖率。采用 beam width 4 "
     "和选定模板库时，端到端成功率在 300 个固定目标上为：深度 ≤2 **47.67%**（143/300），"
     "深度 ≤3 **72.33%**（217/300）。300 个目标中有 207 个至少有一条被标为可用的路线。",
     "逆向搜索报两个覆盖率，必须分开读。在 5,002 个目标的子集上、配 79,184 条模板的库，"
     "any-hit 覆盖率为 **94.74%**（4,739/5,002，Wilson 95% CI 94.09–95.33%）。"
     "在全量 50,016 个目标上、配 3,065 条模板的泄漏剔除库，覆盖率为 **79.81%**。"
     "这个落差同时来自更小的模板库和更大更难的目标集。\n\n"
     "采用 beam width 4 和选定模板库时，端到端成功率在 300 个固定目标上为："
     "深度 ≤2 **47.67%**（143/300，Wilson 95% CI 42.08–53.31%），"
     "深度 ≤3 **72.33%**（217/300，CI 67.01–77.09%）。"
     "300 个目标中有 207 个至少有一条被标为可用的路线。"),
    # 4. methods: backward comparability + beam + usable
    ("覆盖率使用泄漏受控模板库；多步成功率在 300 个目标上用受限 beam 搜索评价。",
     "覆盖率报两个口径：5,002 个目标配 79,184 条模板，50,016 个目标配 3,065 条泄漏剔除库。"
     "两组目标集和两个模板库都不同，覆盖率不能互相比较。"
     "多步成功率在 300 个目标上评价，beam width 4，每次扩展最多 400 个切断。"
     "一条路线在每一步都通过 `retro_search.step_usability` 检查时才算可用，"
     "一个目标只要有一条这样的路线就算可用。"),
    # 5. top-k design note
    ("基线配置是引擎默认值：默认候选上限、默认模板池、不启用底物兼容性预筛。",
     "Christos 不对候选排序，所以 any-position 召回是唯一和输出格式对得上的指标。"
     "要报 precision@k 得先造一个排序，而那正是系统刻意不做的。"
     "预期的用法是读者拿候选对着出处逐条看，而不是把第一行当答案。\n\n"
     "基线配置是引擎默认值：默认候选上限、默认模板池、不启用底物兼容性预筛。"),
    # 6. ablation weighting note
    ("cap 从 32 提到 64，召回和候选数都不变；兼容性预筛在这个样本上没有可测的增益。"
     "增益跟的是 cap 提高和模板池扩大这两件事。模板库本身并非处处正确，运行元数据记录了全部设置，便于复现和比较。",
     "cap 从 32 提到 64，召回和候选数都不变；兼容性预筛在这个样本上没有可测的增益。"
     "增益跟的是 cap 提高和模板池扩大这两件事。模板库本身并非处处正确，运行元数据记录了全部设置，便于复现和比较。\n\n"
     "样本和全量回答的是不同的加权问题，两者的差距是预期内的。500 条样本给每个反应类别等配额，"
     "而全量由第 1、2 类主导，这两类占全部反应的 45% 且分数最高。等权因此把基线从全量的 55.43% "
     "拉到 43.96%，把选定配置从 82.32% 拉到 75.22%。样本上的 41.60% 和 75.80% 正好落在这两个等权值旁边。"
     "消融在一个加权下比较各配置，头条数字用另一个。"),
    # 7. duckdb correction
    ("Christos 用 Python 3.12 实现，依赖 RDKit、rdchiral、SmartReact、DuckDB 和 SQLite。",
     "Christos 用 Python 3.12 实现，依赖 RDKit、rdchiral、SmartReact 和 SQLite。"
     "DuckDB 只出现在生成基准表的离线分析脚本里，不在运行时。"),
    # 8. limitation 9
    ("8. **中医药数据层无法从公开包重算。** 药材、方剂和药典表受第三方条款约束，不随仓库分发。"
     "Demo 只带固定摘录，所以本论文里的中医药规模数字无法只靠公开包复现。",
     "8. **中医药数据层无法从公开包重算。** 药材、方剂和药典表受第三方条款约束，不随仓库分发。"
     "Demo 只带固定摘录，所以本论文里的中医药规模数字无法只靠公开包复现。\n"
     "9. **拉丁名路径不可靠。** 27 个用例的审计里，三个双名学名只有一个解析成功，"
     "而那个成功的是错的。中文名和别名路径更强，但都不完整。"),
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
