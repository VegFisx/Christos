# -*- coding: utf-8 -*-
# One-shot: replace free-text solvent/catalyst/atmosphere with pick-lists,
# and make "custom" the default preset.
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

SOLVENTS = [("water", "水"), ("aqueous", "水溶液"), ("ethanol", "乙醇"),
            ("methanol", "甲醇"), ("organic", "有机溶剂"),
            ("oil", "油"), ("none", "无溶剂")]
CATALYSTS = [("none", "无"), ("acid", "酸"), ("base", "碱"),
             ("metal", "金属"), ("enzyme", "酶"), ("light", "光照")]
ATMOSPHERES = [("air", "空气"), ("O2", "氧气"), ("N2", "氮气"),
               ("H2", "氢气"), ("vacuum", "真空"), ("CO2", "二氧化碳")]


def opts(pairs, sel=None):
    out = []
    for v, label in pairs:
        mark = " selected" if v == sel else ""
        out.append("<option value='%s'%s>%s</option>" % (v, mark, label))
    return "".join(out)


EDITS = [
    # 主表单：三个自由输入改成下拉
    ("<label class='field' title='留空则沿用所选条件档案'>溶剂<input id='c_solvent' "
     "placeholder='water / ethanol'></label>",
     "<label class='field'>溶剂<select id='c_solvent'>%s</select></label>"
     % opts(SOLVENTS, "water")),
    ("<label class='field'>催化剂<input id='c_catalyst' placeholder='none / acid / "
     "base / metal / enzyme'></label>",
     "<label class='field'>催化剂<select id='c_catalyst'>%s</select></label>"
     % opts(CATALYSTS, "none")),
    ("<label class='field'>气氛<input id='c_atmosphere' placeholder='air / O2 / H2 / "
     "N2'></label>",
     "<label class='field'>气氛<select id='c_atmosphere'>%s</select></label>"
     % opts(ATMOSPHERES, "air")),
    # 方剂表单
    ("<label class='field'>溶剂<input id='fc_solvent' placeholder='water / ethanol'></label>",
     "<label class='field'>溶剂<select id='fc_solvent'>%s</select></label>"
     % opts(SOLVENTS, "water")),
    ("<label class='field'>催化剂<input id='fc_catalyst' placeholder='none / acid / "
     "base / metal / enzyme'></label>",
     "<label class='field'>催化剂<select id='fc_catalyst'>%s</select></label>"
     % opts(CATALYSTS, "none")),
    ("<label class='field'>气氛<input id='fc_atmosphere' placeholder='air / O2 / H2 / "
     "N2'></label>",
     "<label class='field'>气氛<select id='fc_atmosphere'>%s</select></label>"
     % opts(ATMOSPHERES, "air")),
    # 预设默认改成「自定义」
    ("<select id='cond'><option value='煎煮' selected>煎煮</option>",
     "<select id='cond'><option value='煎煮'>煎煮</option>"),
    ("<option value='自定义'>自定义…</option></select>",
     "<option value='自定义' selected>自定义…</option></select>"),
    ("<select id='f_cond'><option value='煎煮' selected>煎煮</option>",
     "<select id='f_cond'><option value='煎煮'>煎煮</option>"),
]


def main() -> int:
    s = P.read_text(encoding="utf-8")
    for i, (old, new) in enumerate(EDITS, 1):
        n = s.count(old)
        print("edit %d hits=%d" % (i, n))
        if n:
            s = s.replace(old, new, 1)
    # 方剂页的自定义选项也要加 selected
    old_f = ("<option value='无氧煎煮'>无氧煎煮</option></select></label>")
    new_f = ("<option value='无氧煎煮'>无氧煎煮</option>"
             "<option value='自定义' selected>自定义…</option></select></label>")
    if s.count(old_f):
        s = s.replace(old_f, new_f, 1)
        print("f_cond custom option added")
    P.write_text(s, encoding="utf-8", newline="\n")
    print("written %d chars" % len(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
