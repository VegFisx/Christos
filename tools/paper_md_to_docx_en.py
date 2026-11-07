# -*- coding: utf-8 -*-
"""Convert the English manuscript markdown to DOCX (Latin fonts, PeerJ-ish layout)."""
import re, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

SRC = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\paper-draft-en-20261019.md")
DST = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\paper-draft-en-20261019.docx")
BASE = SRC.parent
doc = Document()
sec = doc.sections[0]
sec.left_margin = sec.right_margin = Cm(2.3)
sec.top_margin = sec.bottom_margin = Cm(2.2)

n = doc.styles['Normal']
n.font.name = 'Times New Roman'; n.font.size = Pt(10.5)
n.element.rPr.rFonts.set(qn('w:eastAsia'), 'SimSun')
n.paragraph_format.line_spacing = 1.4; n.paragraph_format.space_after = Pt(4)

def add_inline(par, text, size=None, italic=False):
    for tok in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text):
        if not tok: continue
        if tok.startswith('**') and tok.endswith('**') and len(tok) > 4:
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith('`') and tok.endswith('`') and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.font.name = 'Courier New'
        else:
            r = par.add_run(tok)
        if size: r.font.size = Pt(size)
        if italic: r.italic = True

md = SRC.read_text(encoding='utf-8').splitlines()
i = 0; nimg = 0
while i < len(md):
    s = md[i].strip()
    if not s or s == '---' or s.startswith('<!--'):
        i += 1; continue
    m = re.match(r'^!\[[^\]]*\]\(([^)]+)\)$', s)
    if m:
        img = BASE / m.group(1)
        if img.exists():
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(img), width=Cm(15.0)); nimg += 1
        i += 1
        j = i
        while j < len(md) and not md[j].strip(): j += 1
        if j < len(md) and md[j].strip().startswith('**Figure'):
            cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_inline(cap, md[j].strip(), size=9)
            i = j + 1
        continue
    if s.startswith('|'):
        rows = []
        while i < len(md) and md[i].strip().startswith('|'):
            rows.append([c.strip() for c in md[i].strip().strip('|').split('|')]); i += 1
        rows = [r for r in rows if not re.match(r'^:?-{2,}', r[0] or '')]
        if rows:
            cols = max(len(r) for r in rows)
            t = doc.add_table(rows=0, cols=cols); t.style = 'Table Grid'; t.autofit = True
            for ri, r in enumerate(rows):
                cells = t.add_row().cells
                for ci in range(cols):
                    par = cells[ci].paragraphs[0]
                    par.paragraph_format.space_after = Pt(1)
                    add_inline(par, r[ci] if ci < len(r) else '', size=8.5)
                    if ri == 0:
                        for run in par.runs: run.bold = True
            doc.add_paragraph()
        continue
    if s.startswith('# '):
        ttl = doc.add_paragraph(); ttl.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = ttl.add_run(s[2:]); r.bold = True; r.font.size = Pt(16); r.font.name = 'Arial'
        ttl.paragraph_format.space_after = Pt(12)
    elif s.startswith('## '):
        h = doc.add_heading(level=1); r = h.add_run(s[3:])
        r.font.name = 'Arial'; r.font.size = Pt(13); r.font.color.rgb = RGBColor(0, 0, 0)
    elif s.startswith('### '):
        h = doc.add_heading(level=2); r = h.add_run(s[4:])
        r.font.name = 'Arial'; r.font.size = Pt(11); r.font.color.rgb = RGBColor(0, 0, 0)
    elif s.startswith('> '):
        p = doc.add_paragraph(); add_inline(p, s[2:], size=9, italic=True)
        for run in p.runs: run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    elif s.startswith('- '):
        p = doc.add_paragraph(style='List Bullet'); add_inline(p, s[2:])
    elif re.match(r'^\d+\. ', s):
        p = doc.add_paragraph(style='List Number'); add_inline(p, re.sub(r'^\d+\. ', '', s))
    elif s.startswith('**Table'):
        p = doc.add_paragraph(); add_inline(p, s, size=9); p.paragraph_format.space_before = Pt(8)
    else:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY; add_inline(p, s)
    i += 1

doc.save(DST)
d = Document(DST)
print('paragraphs', len(d.paragraphs), 'tables', len(d.tables), 'images', nimg)
print('chars', sum(len(p.text) for p in d.paragraphs))
print('saved', DST)