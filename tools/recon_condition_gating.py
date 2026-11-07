# -*- coding: utf-8 -*-
r"""侦察：条件表 + 正向引擎入口。只打印形状，不拉全文。"""
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
COND = STAGE / "reports" / "conditions_by_reaction_type.json"

print("=" * 88)
print("① 条件表 conditions_by_reaction_type.json")
print("=" * 88)
d = json.loads(COND.read_text(encoding="utf-8"))
print("顶层类型:", type(d).__name__, " 条数:", len(d))
if isinstance(d, dict):
    keys = list(d)[:5]
    print("前 5 个 key:", keys)
    k0 = keys[0]
    print(f"\n--- 示例 {k0} ---")
    print(json.dumps(d[k0], ensure_ascii=False, indent=2)[:1200])
    # 统计每个反应类型有哪些字段
    fields = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for f in v:
                fields[f] = fields.get(f, 0) + 1
    print("\n各字段出现次数（总类型数 %d）:" % len(d))
    for f, n in sorted(fields.items(), key=lambda x: -x[1]):
        print(f"   {f:<24} {n}")

print()
print("=" * 88)
print("② 正向引擎入口")
print("=" * 88)
for p in (STAGE / "core" / "engine.py", STAGE / "core" / "smartreact_engine.py"):
    if not p.exists():
        continue
    txt = p.read_text(encoding="utf-8", errors="replace")
    print(f"\n--- {p.name}（{len(txt.splitlines())} 行）---")
    for line in txt.splitlines():
        s = line.strip()
        if re.match(r"^(def |class )", s):
            print("   " + s[:110])
    print("   [关键词命中]")
    for kw in ("conditions", "condition", "temperature", "solvent", "reagent",
               "thermo", "score", "def predict"):
        n = len(re.findall(re.escape(kw), txt, re.I))
        if n:
            print(f"      {kw:<14} {n}")
