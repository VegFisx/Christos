# -*- coding: utf-8 -*-
# One-shot: mirror the six AI-tell fixes into the Chinese draft.
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
    ("针对 33 分钟的全量运行试了四个方向，都没有改变结果——这件事本身就是测量。",
     "针对 33 分钟的全量运行试了四个方向，结果都没有变化。"),
    ("这两样目前都不存在，都属于数据工程问题，也都可以做。",
     "这两样目前都不存在，做起来是数据工程。"),
    ("当前构建不应被描述成支持常见中药的植物名查询。",
     "当前构建不支持常见中药的植物名查询。"),
    ("它的用途是让溯源声明保持可核查，而不是只能被相信。",
     "它让溯源声明可以被核查，不必只靠信任。"),
    ("字段永远填满，字段背后的证据通常不存在。",
     "字段始终是填满的，填在条件字段背后的东西通常不是。"),
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
