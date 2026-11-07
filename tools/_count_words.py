import sys
from pathlib import Path
from docx import Document
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
p = Path(r'D:\ProgramData\DSHNS\chemreact-staging\reports\paper\submission\manuscript.docx')
d = Document(p)
main = 0; started = False
for par in d.paragraphs:
    t = par.text.strip()
    if t == 'References': break
    if t.startswith('Introduction'): started = True
    if started: main += len(t.split())
allw = sum(len(par.text.split()) for par in d.paragraphs)
pdf = p.with_suffix('.pdf').read_bytes()
print('words_main_text', main)
print('words_total_incl_refs', allw)
print('pdf_signature', pdf[:5])
print('pdf_bytes', len(pdf))