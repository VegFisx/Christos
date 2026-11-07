# -*- coding: utf-8 -*-
# One-shot: rebuild the component-limit tiers as 24 / 64 / 128 / all.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD_MAIN = ("<select id='limit'><option>6</option><option>12</option>"
            "<option>24</option><option value='all' selected>全部（较慢）</option></select>")
NEW_MAIN = ("<select id='limit'><option>24</option><option>64</option>"
            "<option>128</option><option value='all' selected>全部（较慢）</option></select>")

OLD_F = ("<select id='f_limit'><option>2</option><option>6</option>"
         "<option>12</option><option>24</option>"
         "<option value='all' selected>全部（较慢）</option></select>")
NEW_F = ("<select id='f_limit'><option>24</option><option>64</option>"
         "<option>128</option><option value='all' selected>全部（较慢）</option></select>")

OLD_SET = ("<select id='set_limit'><option>6</option><option>12</option>"
           "<option>24</option><option value='all' selected>全部</option></select>")
NEW_SET = ("<select id='set_limit'><option>24</option><option>64</option>"
           "<option>128</option><option value='all' selected>全部</option></select>")

OLD_HINT = ("每味成分实测（甘草）：3 / 6 / 12 / 24 / 48 个分别约 1 / 2 / 4 / 19 / 93 秒；"
            "产物数随成分数的平方增长。默认取全部，按需下调可以明显缩短等待。")
NEW_HINT = ("每味成分（甘草 359 个）：24 个约 19 秒、覆盖全部 17 个 marker；64 个约 2.8 分钟；"
            "128 个约 11 分钟（外推）；全部约 90 分钟（外推）。产物与耗时都随成分数的平方增长，"
            "默认取全部。")

OLD_TITLE = ("title='实测（甘草）：3/6/12/24/48 个成分分别约 1/2/4/19/93 秒，"
             "产物数随成分数的平方增长；排序为 marker 优先、分子量降序'")
NEW_TITLE = ("title='实测（甘草 359 个成分）：24 个约 19 秒并覆盖全部 17 个 marker，"
             "64 个约 2.8 分钟，128 个约 11 分钟（外推），全部约 90 分钟（外推）；"
             "排序为 marker 优先、分子量降序'")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate([
        (OLD_MAIN, NEW_MAIN),
        (OLD_F, NEW_F),
        (OLD_SET, NEW_SET),
        (OLD_HINT, NEW_HINT),
        (OLD_TITLE, NEW_TITLE),
    ], 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
