# -*- coding: utf-8 -*-
"""核对③：多路线输出确实返回多条不同路线。"""
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
STAGE = Path(r'D:/ProgramData/DSHNS/chemreact-staging')
for _p in (STAGE/'tools', STAGE/'libs', Path(r'D:/TCMAI/src')):
    sys.path.insert(0, str(_p))
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')
from retro_search import (RetroSearch, load_available, load_purchasable_blocks,
                          load_rdchiral_templates)
av = load_available()
bf, bs = load_purchasable_blocks(False)
eng = RetroSearch(load_rdchiral_templates(), av, blocks_full=bf, blocks_skel=bs,
                  filter_weird=True, weird_charged=True, skel_tol=1)
for t in ['CCNC(C)=O', 'O=C(NCCc1ccc(O)cc1)c1ccccc1O', 'COc1cc(CC=C(C)C)cc(OC)c1O']:
    routes, stat = eng.search(t, max_depth=3, beam=4, max_routes=3)
    print('=' * 80)
    print(f'目标 {t}  ->  {len(routes)} 条路线   统计 {stat}')
    for i, r in enumerate(routes[:3], 1):
        print(f'  路线{i} ({len(r.steps)}步): ' + ' | '.join(
            f'[{s.reaction_name}] ' + ' + '.join(s.precursors) for s in r.steps))
        print(f'      终点: {r.terminals}')