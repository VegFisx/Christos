# -*- coding: utf-8 -*-
# One-shot: make the round count self-explanatory and default the component
# limit to "all", per reviewer feedback.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

EDITS = [
    ("<span class='hint'>默认保守设置</span>",
     "<span class='hint'>轮数 = 反应迭代次数（上一轮产物继续当下一轮底物），"
     "不是反复煎煮</span>"),
    ("<label class='field'>轮数<select id='rounds'>",
     "<label class='field' title='上一轮产物继续作为下一轮底物；与煎煮次数无关'>"
     "反应轮数<select id='rounds'>"),
    ("<label class='field'>轮数<select id='f_rounds'>",
     "<label class='field' title='上一轮产物继续作为下一轮底物；与煎煮次数无关'>"
     "反应轮数<select id='f_rounds'>"),
    ("<label class='field'>默认轮数<select id='set_rounds'>",
     "<label class='field'>默认反应轮数<select id='set_rounds'>"),
    ("<label class='field'>每味取几个成分<select id='limit'><option>6</option>"
     "<option selected>12</option><option>24</option>"
     "<option value='all'>全部（较慢）</option></select></label>",
     "<label class='field' title='成分越多覆盖越全也越慢；排序为 marker 优先、"
     "分子量降序'>每味取几个成分<select id='limit'><option>6</option>"
     "<option>12</option><option>24</option>"
     "<option value='all' selected>全部（较慢）</option></select></label>"),
    ("<select id='f_limit'><option selected>2</option><option>6</option>"
     "<option>12</option><option>24</option>"
     "<option value='all'>全部（较慢）</option></select>",
     "<select id='f_limit'><option>2</option><option>6</option>"
     "<option>12</option><option>24</option>"
     "<option value='all' selected>全部（较慢）</option></select>"),
    ("<select id='set_limit'><option>6</option><option selected>12</option>"
     "<option>24</option><option value='all'>全部</option></select>",
     "<select id='set_limit'><option>6</option><option>12</option>"
     "<option>24</option><option value='all' selected>全部</option></select>"),
    ("<label class='field'>对子预算<input id='max_pairs' value='4000'></label>",
     "<label class='field' title='底物两两配对的上限；4000 约等于 90 个成分的全部配对，"
     "超出部分会被截断'>对子预算<input id='max_pairs' value='4000'></label>"),
]


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(EDITS, 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
