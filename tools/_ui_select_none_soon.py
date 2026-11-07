# -*- coding: utf-8 -*-
# One-shot: put a working "none" first and a disabled "coming soon" last.
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\integration\tcmai_bridge"
         r"\ui_page.html")

SOON = "<option disabled>（敬请期待）</option>"

SOLVENTS = ([("<option value='none'>无溶剂</option>", "<option value='none'>无</option>")]
            + [(x, x) for x in []])

WANT = {
    "c_solvent": ["none", "water", "aqueous", "ethanol", "methanol", "organic", "oil"],
    "fc_solvent": ["none", "water", "aqueous", "ethanol", "methanol", "organic", "oil"],
    "c_catalyst": ["none", "acid", "base", "metal", "enzyme", "light"],
    "fc_catalyst": ["none", "acid", "base", "metal", "enzyme", "light"],
    "c_atmosphere": ["none", "air", "O2", "N2", "H2", "vacuum", "CO2"],
    "fc_atmosphere": ["none", "air", "O2", "N2", "H2", "vacuum", "CO2"],
}

LABEL = {
    "water": "水", "aqueous": "水溶液", "ethanol": "乙醇", "methanol": "甲醇",
    "organic": "有机溶剂", "oil": "油", "none": "无",
    "acid": "酸", "base": "碱", "metal": "金属", "enzyme": "酶", "light": "光照",
    "air": "空气", "O2": "氧气", "N2": "氮气", "H2": "氢气",
    "vacuum": "真空", "CO2": "二氧化碳",
}


def rebuild(match, sid=None):
    vals = WANT[sid]
    default = "none" if vals[0] == "none" else vals[0]
    parts = []
    for v in vals:
        mark = " selected" if v == default else ""
        parts.append("<option value='%s'%s>%s</option>" % (v, mark, LABEL[v]))
    parts.append(SOON)
    return "<select id='%s'>%s</select>" % (sid, "".join(parts))


def main() -> int:
    s = P.read_text(encoding="utf-8")
    total = 0
    for sid in WANT:
        pat = re.compile(r"<select id='%s'>.*?</select>" % sid, re.S)
        s, n = pat.subn(lambda m, _s=sid: rebuild(m, _s), s)
        print("%-14s replaced=%d" % (sid, n))
        total += n
    P.write_text(s, encoding="utf-8", newline="\n")
    print("total %d, written %d chars" % (total, len(s)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
