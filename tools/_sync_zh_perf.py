# -*- coding: utf-8 -*-
# One-shot: mirror the "what did not help" section into the Chinese draft.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper"
         r"\Christos-system-paper-draft-20261019-zh-humanized.md")

SECTION = "\n".join([
    "### 哪些优化没有奏效",
    "",
    "针对 33 分钟的全量运行试了四个方向，都没有改变结果——这件事本身就是测量。",
    "",
    "跨批复用单底物模板的结果没有效果。1,000 对花掉的 72 秒主要来自 11,000 次 RDKit "
    "`RunReactants` 调用，每次约 6.5 毫秒；单底物路径只占很小一部分。",
    "",
    "直接按索引枚举对子、而不是先建出完整的 58,311 个元组再切片，同样没有变化。",
    "",
    "按 200 对一批把产物流式写盘，峰值内存从 1.8 GB 降到平稳水平，但比 2,000 对切片慢 60%，"
    "因为在这个粒度下每批的固定开销占了大头。",
    "",
    "四进程并行在原理上可行：切片彼此独立，前四片跑出的产物数与串行完全一致。失败在内存——"
    "每个 worker 持有约 1.7 GB 的产物对象，四个 worker 就会吃光 16 GB 机器，其中两个被系统"
    "直接杀掉、连错误栈都来不及留下。瓶颈是单个产物对象的体积，不是模板库：加载全部 "
    "82,000 条模板只占约 37 MB。",
    "",
    "要突破这个上限，需要改变产物对象承载的内容——把出处查询推迟到写盘时再做。这属于引擎层"
    "重构，本文不展开。",
    "",
])

ANCHOR = "## 讨论"


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n = s.count(ANCHOR)
    print("anchor=%d" % n)
    if n:
        s = s.replace(ANCHOR, SECTION + ANCHOR, 1)
        P.write_text(s, encoding="utf-8", newline="\n")
        print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
