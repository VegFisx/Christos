# -*- coding: utf-8 -*-
r"""一次性探针：NTU 同义词表里到底有没有 黄耆 / 桂心 / 官桂 / 胆星 …？"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

XLS = Path(r"D:\TCMAI\data\ChineseDrugEthnonymsSynonymyTable.xlsx")
KEYS = ("黄耆", "桂心", "官桂", "胆星", "炙草", "归尾", "归身", "龟版", "桑皮", "芒消")

z = zipfile.ZipFile(XLS)
shared = []
if "xl/sharedStrings.xml" in z.namelist():
    sx = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
    shared = re.findall(r"<t[^>]*>(.*?)</t>", sx, re.S)
sx = z.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
rows = re.findall(r"<row[^>]*>(.*?)</row>", sx, re.S)

def cell_texts(row: str) -> list:
    out = []
    for m in re.finditer(r'<c[^>]*r="[A-Z]+\d+"([^>]*)>(.*?)</c>', row, re.S):
        attrs, body = m.group(1), m.group(2)
        t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
        v = re.search(r"<v>(.*?)</v>", body, re.S)
        if t:
            out.append(t.group(1))
        elif v:
            val = v.group(1)
            if 't="s"' in attrs and val.isdigit() and int(val) < len(shared):
                val = shared[int(val)]
            out.append(val)
    return out

print("总行数 =", len(rows))
for k in KEYS:
    hits = []
    for r in rows[1:]:
        cells = cell_texts(r)
        if any(k == c.strip() for c in cells):
            hits.append([c for c in cells if c][:5])
            if len(hits) >= 2:
                break
    print("  %-4s → %s" % (k, hits or "（表里没有这个字面）"))
