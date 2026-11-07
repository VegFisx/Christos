# -*- coding: utf-8 -*-
"""Convert the paper draft markdown into a reviewable DOCX (single source: the .md)."""
import re, sys
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
SRC = Path(os.environ.get("PAPER_SRC", r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\论文-初稿-20261019.md"))
DST = Path(os.environ.get("PAPER_DST", str(SRC.with_suffix(".docx"))))
BASE = SRC.parent
doc = Document()

sec = doc.sections[0]
sec.left_margin = sec.right_margin = Cm(2.4)
sec.top_margin = sec.bottom_margin = Cm(2.2)

normal = doc.styles['Normal']
normal.font.name = 'Times New Roman'
normal.font.size = Pt(10.5)
normal.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
normal.paragraph_format.line_spacing = 1.45
normal.paragraph_format.space_after = Pt(4)

def set_east(run, font):
    run.font.name = font
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font)

def add_inline(par, text, size=None, italic=False):
    # split on **bold** and `code`
    for tok in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text):
        if not tok:
            continue
        if tok.startswith('**') and tok.endswith('**') and len(tok) > 4:
            r = par.add_run(tok[2:-2]); r.bold = True
        elif tok.startswith('`') and tok.endswith('`') and len(tok) > 2:
            r = par.add_run(tok[1:-1]); r.font.name = 'Consolas'
        else:
            r = par.add_run(tok)
        if size: r.font.size = Pt(size)
        if italic: r.italic = True

md = SRC.read_text(encoding='utf-8').splitlines()
i = 0
n_img = 0
while i < len(md):
    line = md[i].rstrip()
    s = line.strip()
    if not s:
        i += 1; continue
    if s == '---':
        i += 1; continue
    m = re.match(r'^!\[[^\]]*\]\(([^)]+)\)$', s)
    if m:
        img = BASE / m.group(1)
        if img.exists():
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(img), width=Cm(15.5))
            n_img += 1
        i += 1
        # caption on next non-empty line
        j = i
        while j < len(md) and not md[j].strip():
            j += 1
        if j < len(md) and md[j].strip().startswith('*') and md[j].strip().endswith('*'):
            cap = doc.add_paragraph(); cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(cap, md[j].strip().strip('*'), size=9, italic=True)
            i = j + 1
        continue
    if s.startswith('|'):
        rows = []
        while i < len(md) and md[i].strip().startswith('|'):
            rows.append([c.strip() for c in md[i].strip().strip('|').split('|')])
            i += 1
        rows = [r for r in rows if not re.match(r'^:?-{2,}', r[0] or '')]
        if rows:
            cols = max(len(r) for r in rows)
            t = doc.add_table(rows=0, cols=cols)
            t.style = 'Table Grid'
            for ri, r in enumerate(rows):
                cells = t.add_row().cells
                for ci in range(cols):
                    txt = r[ci] if ci < len(r) else ''
                    par = cells[ci].paragraphs[0]
                    add_inline(par, txt, size=9)
                    if ri == 0:
                        for run in par.runs:
                            run.bold = True
            doc.add_paragraph()
        continue
    if s.startswith('# '):
        ttl = doc.add_paragraph(); ttl.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = ttl.add_run(s[2:]); r.bold = True; r.font.size = Pt(17); set_east(r, '黑体')
        ttl.paragraph_format.space_after = Pt(10)
    elif s.startswith('## '):
        h = doc.add_heading(level=1)
        r = h.add_run(s[3:]); set_east(r, '黑体')
        r.font.size = Pt(14); r.font.color.rgb = RGBColor(0, 0, 0)
    elif s.startswith('### '):
        h = doc.add_heading(level=2)
        r = h.add_run(s[4:]); set_east(r, '黑体')
        r.font.size = Pt(12); r.font.color.rgb = RGBColor(0, 0, 0)
    elif s.startswith('> '):
        p = doc.add_paragraph()
        add_inline(p, s[2:], size=9, italic=True)
        for run in p.runs:
            run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    elif re.match(r'^- ', s):
        p = doc.add_paragraph(style='List Bullet')
        add_inline(p, s[2:])
    elif re.match(r'^\d+\. ', s):
        p = doc.add_paragraph(style='List Number')
        add_inline(p, re.sub(r'^\d+\. ', '', s))
    else:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_inline(p, s)
    i += 1

doc.save(DST)
d = Document(DST)
print('paragraphs', len(d.paragraphs), 'tables', len(d.tables), 'images', n_img)
print('words(chars)', sum(len(p.text) for p in d.paragraphs))
print('saved', DST)