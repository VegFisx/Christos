# -*- coding: utf-8 -*-
"""一次性探针：引擎真正加载的 conditions_normalized.json 里 4 类反应的门控字段。"""
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

R = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports")
for nm in ("conditions_normalized.json", "conditions_by_reaction_type.json",
           "aux_reagent_coverage.json"):
    p = R / nm
    print(f"{nm:<38} exists={p.exists()}  size={p.stat().st_size if p.exists() else 0:,}")
print()

p = R / "conditions_normalized.json"
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"normalized 条目数={len(d)}")
    for k in ("mitsunobu", "suzuki", "amide_coupling", "esterification",
              "appel", "wittig", "reductive_amination"):
        e = d.get(k)
        if not e:
            print(f"  {k:<20} <缺失>")
            continue
        t = e.get("temp_C") or {}
        print(f"  {k:<20} n={e.get('n_ord_matched')} "
              f"T=[{t.get('min')},{t.get('max')}] def={t.get('default')}")
        print(f"  {'':<20} 溶剂 {e.get('solvents')}")
        print(f"  {'':<20} 辅助 {e.get('auxiliary_reagents')}")
    print()
    print("--- 全表：溶剂形态分布（归一名是否已生效） ---")
    c = Counter()
    for k, e in d.items():
        for s in (e.get("solvents") or []):
            c[str(s)] += 1
    print(f"  归一名 {len(c)} 个: {sorted(c)[:40]}")
