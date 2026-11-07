# -*- coding: utf-8 -*-
r"""一次性探针：SymMap v2.0 的药材表里有没有「中文名 → 拉丁/物种」？"""
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

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")


def sheet_rows(f: Path, n: int = 6):
    z = zipfile.ZipFile(f)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        sx = z.read("xl/sharedStrings.xml").decode("utf-8", errors="replace")
        shared = re.findall(r"<t[^>]*>(.*?)</t>", sx, re.S)
    sx = z.read("xl/worksheets/sheet1.xml").decode("utf-8", errors="replace")
    out = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", sx, re.S)[:n]:
        cells = []
        for c in re.findall(r'<c[^>]*r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', row, re.S):
            ref, attrs, body = c
            v = re.search(r"<v>(.*?)</v>", body, re.S)
            t = re.search(r'<t[^>]*>(.*?)</t>', body, re.S)
            if t:
                cells.append(t.group(1))
            elif v:
                val = v.group(1)
                if 't="s"' in attrs and val.isdigit() and int(val) < len(shared):
                    val = shared[int(val)]
                cells.append(val)
        out.append(cells)
    return out


for f in sorted((STAGE / "data" / "symmap").glob("*.xlsx")):
    print("=" * 90)
    print(f.name)
    for r in sheet_rows(f, 5):
        print("   ", r[:10])
