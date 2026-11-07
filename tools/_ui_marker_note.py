# -*- coding: utf-8 -*-
# One-shot: describe the specificity ordering in the UI.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD_TITLE = ("title='实测（甘草 359 个成分）：24 个约 19 秒并覆盖全部 17 个 marker，"
             "64 个约 2.8 分钟，128 个约 7.1 分钟（实测）；全部 359 个曾因内存耗尽中断，"
             "建议先存盘或改用 128；排序为 marker 优先、分子量降序'")
NEW_TITLE = ("title='排序按「该成分出现在几个药材里」升序：只出现在本药材的排最前，"
             "Beta-sitosterol 这类出现在 534 个药材的通用成分垫底。"
             "实测（甘草 359 个成分）：24 个约 19 秒，64 个约 2.8 分钟，"
             "128 个约 7.1 分钟；全部 359 个曾因内存耗尽中断，建议先存盘或改用 128'")

OLD_HINT = ("每味成分（甘草 359 个）：24 个约 19 秒、覆盖全部 17 个 marker；"
            "64 个约 2.8 分钟；128 个约 7.1 分钟（实测）；"
            "全部 359 个在 64,261 对规模下曾因内存耗尽而中断，建议先存盘再跑，或改用 128。"
            "产物与耗时都随成分数的平方增长，默认取全部。")
NEW_HINT = ("每味成分排序规则：按「该成分出现在几个药材里」升序——只属于本药材的排最前，"
            "常见的通用成分（如 Beta-sitosterol，出现在 534 个药材）垫底。"
            "实测（甘草 359 个）：24 个约 19 秒并覆盖全部主要专属成分，"
            "64 个约 2.8 分钟，128 个约 7.1 分钟，全部因内存耗尽需切片执行。")

OLD_HINT2 = ("每味成分实测（甘草）：3 / 6 / 12 / 24 / 48 个分别约 1 / 2 / 4 / 19 / 93 秒；"
             "产物数随成分数的平方增长。默认取全部，按需下调可以明显缩短等待。")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(OLD_TITLE)
    n2 = s.count(OLD_HINT)
    n3 = s.count(OLD_HINT2)
    print("hits %d %d %d" % (n1, n2, n3))
    if n1:
        s = s.replace(OLD_TITLE, NEW_TITLE, 1)
    if n2:
        s = s.replace(OLD_HINT, NEW_HINT, 1)
    elif n3:
        s = s.replace(OLD_HINT2, NEW_HINT, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
