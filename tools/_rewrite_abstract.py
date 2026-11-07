import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
p = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\paper-draft-en-20261019.md')
t = p.read_text(encoding='utf-8')
reps = [
 ('We audit a production template library template by template on the public USPTO-50k benchmark and on Open Reaction Database reactions, under a leak-controlled protocol, and release a reproducible audit-and-repair framework.',
  'We audit a production template library on the public USPTO-50k benchmark and on Open Reaction Database reactions, under a leak-controlled protocol, and release a reproducible audit-and-repair framework.'),
 ('the top five templates alone contributing 52.7%', 'top five templates contributing 52.7%'),
 ('Throughout, we mark rather than delete, never rank silently, and attach provenance to every generated item.',
  'We mark rather than delete, never rank silently, and attach provenance to every item.'),
]
for a, b in reps:
    if a in t:
        t = t.replace(a, b)
    else:
        print('MISS', a[:40])
p.write_text(t, encoding='utf-8')
a = t.split('## Abstract',1)[1].split('**Keywords:**')[0]
print('abstract words', len(a.split()))