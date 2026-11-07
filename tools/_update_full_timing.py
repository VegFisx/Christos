# -*- coding: utf-8 -*-
# One-shot: replace the extrapolated full-run figure with the measured one.
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UI = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
          r"\ui_page.html")
EN = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\arxiv-20261020"
          r"\manuscript-humanized.md")
ZH = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
          r"\Christos-system-paper-draft-20261019-zh-humanized.md")

OLD_UI = ("每味成分（甘草 359 个）：24 个约 19 秒、覆盖全部 17 个 marker；"
          "64 个约 2.8 分钟；128 个约 7.1 分钟（实测）；"
          "全部 359 个在 64,261 对规模下曾因内存耗尽而中断，建议先存盘再跑，或改用 128。"
          "产物与耗时都随成分数的平方增长，默认取全部。")
NEW_UI = ("每味成分（甘草 342 个去重后成分）：24 个约 19 秒，64 个约 2.8 分钟，"
          "128 个约 7.1 分钟，全部 342 个（58,311 对）切片执行约 33 分钟、"
          "得到 35.9 万条产物（切片内去重，跨片未去重，属上界）。"
          "产物与耗时都随成分数平方增长，默认取全部。")

OLD_EN_ROW = "| 128 | 128 | 8,128 | 97,670 | 429 s |"
NEW_EN_ROW = "\n".join([
    "| 128 | 128 | 8,128 | 97,670 | 429 s |",
    "| 342 (all) | 342 | 58,311 | 359,141 (upper bound) | 33 min |",
])

OLD_EN_NOTE = ("At 24 compounds a run covers all 17 marker compounds of Glycyrrhiza. Going to 128 "
               "adds products but no new markers, so the useful default for marker-level work is 24 "
               "and the larger tiers exist for exhaustive enumeration.")
NEW_EN_NOTE = ("At 24 compounds a run covers every characteristic compound of Glycyrrhiza under the "
               "specificity ordering. Going to 128 adds products but no new characteristic entries. "
               "The full set needs slicing: run as 30 slices of 2,000 pairs each, it completes in 33 "
               "minutes and yields 359,141 products where each slice is deduplicated internally and "
               "duplicates across slices are not removed, so the figure is an upper bound.")

OLD_ZH_ROW = "| 128 | 128 | 8,128 | 97,670 | 429 s |"
NEW_ZH_ROW = "\n".join([
    "| 128 | 128 | 8,128 | 97,670 | 429 s |",
    "| 342（全部） | 342 | 58,311 | 359,141（上界） | 33 分钟 |",
])

OLD_ZH_NOTE = ("24 个成分就覆盖甘草全部 17 个 marker。加到 128 只增加产物、不增加 marker，"
               "所以 marker 级别的工作用 24，大档留给穷举。")
NEW_ZH_NOTE = ("24 个成分在特异性排序下已覆盖甘草全部特征成分。加到 128 只增加产物、"
               "不增加特征条目。全量必须切片：按每 2,000 对一个切片，30 片共 33 分钟跑完，"
               "得到 35.9 万条产物——切片内去重、跨片不去重，所以是上界。")


def patch(path, pairs):
    s = path.read_text(encoding="utf-8")
    for old, new in pairs:
        n = s.count(old)
        print("%s: %d" % (path.name, n))
        if n:
            s = s.replace(old, new, 1)
    path.write_text(s, encoding="utf-8", newline="\n")


def main() -> int:
    patch(UI, [(OLD_UI, NEW_UI)])
    patch(EN, [(OLD_EN_ROW, NEW_EN_ROW), (OLD_EN_NOTE, NEW_EN_NOTE)])
    patch(ZH, [(OLD_ZH_ROW, NEW_ZH_ROW), (OLD_ZH_NOTE, NEW_ZH_NOTE)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
