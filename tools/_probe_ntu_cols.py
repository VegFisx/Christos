# -*- coding: utf-8 -*-
r"""一次性探针：NTU《中文药名同义词表》里有没有**物种/拉丁**列？"""
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
z = zipfile.ZipFile(XLS)
print("sheet 文件：", [n for n in z.namelist() if n.startswith("xl/worksheets")][:4])
shared = []
if "xl/sharedStrings.xml" in z.namelist():
    sx = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
    shared = re.findall(r"<t[^>]*>(.*?)</t>", sx, re.S)
sx = z.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
rows = re.findall(r"<row[^>]*>(.*?)</row>", sx, re.S)[:5]
for i, row in enumerate(rows, 1):
    cells = []
    for m in re.finditer(r'<c[^>]*r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', row, re.S):
        ref, attrs, body = m.group(1), m.group(2), m.group(3)
        t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
        v = re.search(r"<v>(.*?)</v>", body, re.S)
        if t:
            cells.append(t.group(1))
        elif v:
            val = v.group(1)
            if 't="s"' in attrs and val.isdigit() and int(val) < len(shared):
                val = shared[int(val)]
            cells.append(val)
    print("  行%d：%s" % (i, cells[:8]))
