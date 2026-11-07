# -*- coding: utf-8 -*-
# One-shot: label the presets as engineering reference values.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

OLD = "<label class='field'>基准预设<select id='cond'>"
NEW = ("<label class='field' title='预设为工程代表值，不是药典标准：温度取自沸点或体温，"
       "时长与 pH 为经验取值'>基准预设（示例值）<select id='cond'>")

OLD_NOTE = ("<span class='hint'>直接填参数；留空的项沿用下方预设的值。"
            "预设只是快捷模板，可随时改。</span>")
NEW_NOTE = ("<span class='hint'>直接填参数；选预设会自动填入示例值，可逐项覆盖。"
            "预设是工程代表值，不是药典标准：煎煮 100°C 与醇提 78°C 取自沸点，"
            "酶催化 37°C 取自体温，时长与 pH 为经验取值。"
            "其中“还原”一档需要氢气与金属催化剂，煎煮条件下不会发生，仅供对照。</span>")


def main() -> int:
    s = P.read_text(encoding="utf-8")
    n1 = s.count(OLD)
    n2 = s.count(OLD_NOTE)
    print("hits %d %d" % (n1, n2))
    if n1:
        s = s.replace(OLD, NEW, 1)
    if n2:
        s = s.replace(OLD_NOTE, NEW_NOTE, 1)
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
