# -*- coding: utf-8 -*-
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
p = Path(r'D:/ProgramData/DSHNS/AGENTS.md')
s = p.read_text(encoding='utf-8')
p.write_text(s + "", encoding='utf-8')
print('AGENTS.md 已追加第八节')