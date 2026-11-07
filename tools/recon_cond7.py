# -*- coding: utf-8 -*-
r"""看 Conditions 模型的字段 + REQUIRED_CONDITION_KEYS（决定 profile 能写什么）。"""
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")

print("=" * 92)
print("① Conditions 模型（model.py）")
print("=" * 92)
mp = STAGE / "rules" / "model.py"
txt = mp.read_text(encoding="utf-8", errors="replace")
print(txt[:2200])

print()
print("=" * 92)
print("② REQUIRED_CONDITION_KEYS（schema.py）")
print("=" * 92)
sc = (STAGE / "rules" / "schema.py").read_text(encoding="utf-8", errors="replace")
m = re.search(r"REQUIRED_CONDITION_KEYS\s*=\s*(.+?)\n(?=[A-Z_]|\ndef |\nclass )", sc, re.S)
print(m.group(0)[:600] if m else "没找到 REQUIRED_CONDITION_KEYS")

print()
print("=" * 92)
print("③ activation_score 的其余部分（温度/时间怎么算分）")
print("=" * 92)
ac = (STAGE / "conditions" / "activator.py").read_text(encoding="utf-8", errors="replace")
lines = ac.splitlines()
for i, line in enumerate(lines):
    if "软打分" in line or re.match(r"^def window_score", line.strip()):
        for j in range(i, min(len(lines), i + 26)):
            print(f"   {j+1:>4} {lines[j][:106]}")
        break
