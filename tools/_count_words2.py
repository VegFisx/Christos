import sys
from docx import Document
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
d = Document(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\submission\manuscript-v3.docx')
started = False; main = 0; total = 0
for p in d.paragraphs:
    t = p.text.strip()
    if t == 'References': break
    if t.startswith('Introduction'): started = True
    total += len(t.split())
    if started: main += len(t.split())
print('main', main, 'upto_refs', total)