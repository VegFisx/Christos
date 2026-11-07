import re, sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
cn = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\论文-初稿-20261019.md').read_text(encoding='utf-8')
en = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\paper-draft-en-20261019.md').read_text(encoding='utf-8')
def heads(t):
    return [l.strip('# ').strip() for l in t.splitlines() if l.startswith('## ')]
print('CN chars', len(cn), 'EN chars', len(en))
print('CN headings:', len(heads(cn)))
for h in heads(cn): print('   CN |', h)
print('EN headings:', len(heads(en)))
for h in heads(en): print('   EN |', h)
def nums(t):
    return set(re.findall(r'\d+\.\d+%', t))
a, b = nums(cn), nums(en)
print('only CN pcts:', sorted(a - b))
print('only EN pcts:', sorted(b - a))