# -*- coding: utf-8 -*-
r"""验收：用户看到的坏路线，加护栏前后对比（定性证据）。

用法: python show_before_after.py
"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (STAGE/"tools", STAGE/"libs", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from retro_search import RetroSearch, load_available, load_retro_templates, load_purchasable_blocks

TARGETS = [
    ("Thymidine 胸苷", "CC1=CN(C2CC(O)C(CO)O2)C(=O)N1"),
    ("5-methoxymarmesin", "COc1cc2c(cc1O)oc1cc(O)cc(O)c1c2=O"),
    ("CCNC(C)=O 乙酰胺", "CCNC(C)=O"),
]

tmpl = load_retro_templates(); av = load_available(); bf, bs = load_purchasable_blocks()
engs = {
    "加护栏前": RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                           filter_weird=False, skel_tol=99, weird_charged=False),
    "加护栏后": RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                           filter_weird=True, skel_tol=1, weird_charged=True),
}

for label, smi in TARGETS:
    print("=" * 92)
    print(f"目标: {label}   {smi}")
    print("=" * 92)
    for engname, eng in engs.items():
        dis = eng.disconnections(smi)
        routes = []
        for st in dis:
            hits = [(p, eng.is_available(p)) for p in st.precursors]
            if all(h[1] for h in hits):
                routes.append((st, hits))
        print(f"   [{engname}] 切断方案 {len(dis):>5} 个，"
              f"其中【全部前体可得】的 {len(routes)} 个")
        for st, hits in routes[:3]:
            pre = " + ".join(f"{p}" for p, _ in hits)
            print(f"        [{st.reaction_name}] {pre[:110]}")
    print()
