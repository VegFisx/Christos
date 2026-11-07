# -*- coding: utf-8 -*-
# One-shot: sixth-round fixes for the Chinese draft.
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
    ("多步规划器在 300 个目标上，深度 ≤2/≤3 的成功率分别为 **47.67%/72.33%**。",
     "多步规划器在 300 个 ORD 目标上，深度 ≤2/≤3 的成功率分别为 **47.67%/72.33%**；"
     "与逆向数字不同，这一组没有做目标级过滤。"),
    ("多步规划在深度 ≤2/≤3 时分别达到 47.67%/72.33%。",
     "多步规划在 300 个未做目标级过滤的 ORD 目标上，深度 ≤2/≤3 时分别达到 47.67%/72.33%。"),
    ("精确中文名和别名基本每次都解析成功，两组各有一个歧义结果。",
     "精确中文名 20 个全部解析成功。别名 10 个中成功 9 个，寸冬返回空。"),
    ("十个本不该解析的字符串里，九个返回空。「甘」这个单字返回了 40 个候选，正好撞上子串匹配的上限，因为它能匹配到很多药名。",
     "十个本不该解析的字符串里，九个返回空。「甘」这个单字返回了 40 个候选，正好撞上子串匹配的上限，"
     "因为它能匹配到很多药名。这一次属于错误返回，不是解析成功。"),
    ("审计脚本在仓库里（tools/audit_herb_resolution.py），用例表可以继续扩充。",
     "表内抽出的 25 个双名是容易的那一半。用户按常见药材的植物学名输入这件事，这次只有 "
     "Glycyrrhiza uralensis 一个用例，而且失败了。当前构建不应被描述成支持常见中药的植物名查询。\n\n"
     "审计脚本在仓库里（tools/audit_herb_resolution.py），用例表可以继续扩充。"),
    ("| 非药材字符串 | 10 | 1 | 9 | 1 |",
     "| 非药材字符串 | 10 | 1 | 9 | 1 |\n\n"
     "歧义列统计的是返回多个候选的条目，是“解析成功”的子集，不是独立结果。非药材那一行的 1 个"
     "“解析成功”是错误返回，不是正确解析。"),
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
