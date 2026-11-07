# -*- coding: utf-8 -*-
r"""看 smartreact_engine.py：它有没有 Conditions 参数、枚举入口长什么样。"""
import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
p = STAGE / "core" / "smartreact_engine.py"
txt = p.read_text(encoding="utf-8", errors="replace")
lines = txt.splitlines()
print("=" * 92)
print(f"smartreact_engine.py（{len(lines)} 行）")
print("=" * 92)
for line in lines:
    s = line.strip()
    if re.match(r"^(def |class )", s):
        print("   " + s[:112])
print()
print("[关键词命中]")
for kw in ("Conditions", "condition", "temperature", "solvent", "reagent",
           "activate", "categor", "template"):
    print(f"   {kw:<14} {len(re.findall(re.escape(kw), txt, re.I))}")
print()
print("=" * 92)
print("枚举入口的实现")
print("=" * 92)
for i, line in enumerate(lines):
    if re.match(r"^\s*def (enumerate_pair|run|enumerate_multi|step)", line):
        for j in range(i, min(len(lines), i + 30)):
            print(f"   {j+1:>4} {lines[j][:108]}")
        print()
