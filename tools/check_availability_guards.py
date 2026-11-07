# -*- coding: utf-8 -*-
"""快速核对：加了护栏之后，is_available 的判定对不对（正例/反例各测几个）。"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (STAGE/"tools", STAGE/"libs", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(p))
from retro_search import RetroSearch, load_available, load_retro_templates, load_purchasable_blocks

tmpl = load_retro_templates(); av = load_available(); bf, bs = load_purchasable_blocks()
eng = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs)

CASES = [
    # (smiles, 期望, 说明)
    ("BC(C)=O",                       False, "酰基硼：反转模板的怪前体，不许骨架匹配到阿司匹林"),
    ("BCC",                           False, "烷基硼：不许骨架匹配到对甲酚"),
    ("O=C(O)c1ccccc1O",               True,  "水杨酸：真砌块，应可得"),
    ("CC(=O)O",                       True,  "乙酸：真砌块，应可得"),
    ("O=C(O)c1ccccc1Cl",              True,  "邻氯苯甲酸：差一个取代基，不应被骨架匹配当成水杨酸"),
    ("c1ccccc1",                      True,  "苯：COCONUT 里有，正常"),
    ("O=c1[nH]c(=O)n(C2CC(O)C(CO)O2)cc1I", None, "碘代胸苷类：看它到底算不算可得"),
    ("CC([NH-])=O",                   None,  "酰胺负离子：看判定（带电）"),
]
print(f"{'分子':<44} {'期望':<6} {'实际':<6} {'level':<14} 说明")
bad = 0
for smi, want, note in CASES:
    v = eng.is_available(smi)
    lv = eng._match_level.get(smi, "")
    got = bool(v)
    mark = ""
    if want is not None and got != want:
        mark = "  <<< 不符合期望"
        bad += 1
    print(f"{smi[:44]:<44} {str(want):<6} {str(got):<6} {lv:<14} {note}{mark}")
    if v: print(f"{'':<20}命中来源: {v}")
print()
print("不符合期望的数量:", bad)
