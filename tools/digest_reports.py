# -*- coding: utf-8 -*-
r"""把 reports/ 下所有报告压成一行一案的地图（只取标题行 + 首个要点行，避免通读）。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports")
files = sorted(R.glob("*.md"), key=lambda p: p.stat().st_mtime)
print(f"共 {len(files)} 份报告\n")
for p in files:
    lines = [l.rstrip() for l in p.read_text(encoding="utf-8", errors="replace").splitlines()]
    title = ""
    for l in lines:
        s = l.strip()
        if s.startswith("#"):
            title = s.lstrip("# ").strip()
            break
    bullet = ""
    for l in lines:
        s = l.strip()
        if (s.startswith("- ") or s.startswith("* ")) and len(s) > 12:
            bullet = s[2:].strip()
            break
    t = p.stat().st_mtime
    import datetime
    ts = datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M")
    print(f"{p.name[:34]:<35} {ts}  {title[:60]}")
    if bullet:
        print(f"{'':<35} {'':<12}  · {bullet[:110]}")
