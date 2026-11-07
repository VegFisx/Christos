# -*- coding: utf-8 -*-
# One-shot: apply the fourth-round fixes to the Chinese draft.
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
    # 1. both reverse libraries filtered
    ("逆向模板库用同一套过滤。",
     "逆向用的两个模板库也按同样方式过滤过，只是挖掘来源不同、规模不同："
     "5,002 目标那套用 79,184 条模板，全量 50,016 目标那套用 3,065 条。"),
    # 2. target provenance
    ("多步成功率在 300 个目标上评价，beam width 4，每次扩展最多 400 个切断。",
     "5,002 和 300 两个目标集都取自 ORD，不是 USPTO-50k：筛选条件是分子量不超过 500、单组分、"
     "非盐形式，从 parquet 第 20 万行起取，然后去重。"
     "多步成功率在 300 个目标上评价，beam width 4，每次扩展最多 400 个切断。"),
    # 3. selected config wording
    ("选定配置使用约 2 万条的 support 过滤模板池、每对 cap 32 和兼容性预筛。",
     "选定配置使用约 2 万条的 support 过滤模板池和每对 cap 32。兼容性预筛保留在管线里，"
     "但下面的消融显示它在测试样本上没有可测增益。"),
    # 4. ablation gap is noise
    ("样本上的 41.60% 和 75.80% 正好落在这两个等权值旁边。",
     "样本上的 41.60% 和 75.80% 正好落在这两个等权值旁边。它们的 Wilson 区间分别是 "
     "37.36–45.97% 和 71.86–79.35%，两个等权值都落在区间内，剩下的差距在 n = 500 时属于抽样噪音，"
     "不是系统性偏差。"),
    # 5. conclusion wording
    ("逆向搜索在 5,002 个目标上达到 94.74% 覆盖率；多步规划在深度 ≤2/≤3 时分别达到 47.67%/72.33%。",
     "逆向搜索在 5,002 个目标的子集上达到 94.74% 覆盖率，在全量 50,016 个目标上为 79.81%；"
     "多步规划在深度 ≤2/≤3 时分别达到 47.67%/72.33%。"),
    ("每个候选的来源、规则、条件和不确定性都留着。",
     "每个候选的来源、规则、条件标记以及记录“证据缺失”的旗标都留着。"),
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
