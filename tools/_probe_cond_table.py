# -*- coding: utf-8 -*-
"""一次性探针：conditions_by_reaction_type.json 的形状 + ORD 溶剂名分布。"""
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\conditions_by_reaction_type.json")
d = json.loads(P.read_text(encoding="utf-8"))
print(f"顶层类型 type={type(d).__name__} 条目数={len(d)}")
k0 = next(iter(d))
print(f"键示例: {k0!r}")
print(f"条目字段: {sorted(d[k0].keys())}")
print(f"条目原文: {json.dumps(d[k0], ensure_ascii=False)[:600]}")
print()
print("--- 各字段在整个文件里的形态 ---")
shapes = Counter()
for k, v in d.items():
    for f, val in v.items():
        if isinstance(val, list):
            shapes[(f, "list", len(val))] += 1
        elif isinstance(val, dict):
            shapes[(f, "dict", tuple(sorted(val.keys())))] += 1
        else:
            shapes[(f, type(val).__name__, str(val)[:20])] += 1
for (f, t, extra), n in sorted(shapes.items(), key=lambda x: -x[1])[:24]:
    print(f"  {f:<22} {t:<6} {str(extra)[:60]:<60} x{n}")
print()
print("--- solvents 字段里出现的所有溶剂名（去重） ---")
sc = Counter()
for k, v in d.items():
    for s in (v.get("solvents") or []):
        sc[str(s)] += 1
print(f"  唯一溶剂名 {len(sc)} 个")
for s, n in sc.most_common(60):
    print(f"  {s:<32} 出现在 {n} 类反应里")
