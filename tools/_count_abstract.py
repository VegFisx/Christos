import re, sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
t = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\paper-draft-en-20261019.md').read_text(encoding='utf-8')
a = t.split('## Abstract',1)[1].split('**Keywords:**')[0]
w = len(a.split())
print('abstract words', w)
print(a.strip()[:200])