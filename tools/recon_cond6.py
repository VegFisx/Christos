# -*- coding: utf-8 -*-
r"""条件表数据质量诊断：溶剂名、温度、催化剂到底能不能用来门控。"""
import json
import sys
from collections import Counter
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
cond = json.loads((STAGE / "reports" / "conditions_by_reaction_type.json").read_text(encoding="utf-8"))

print("=" * 92)
print("① temp_C 的完整结构")
print("=" * 92)
for k, v in list(cond.items())[:3]:
    print(f"  {k}: {json.dumps(v.get('temp_C'), ensure_ascii=False)}")
ks = Counter(type(v.get("temp_C")).__name__ for v in cond.values())
print("  temp_C 类型分布:", dict(ks))
has_minmax = sum(1 for v in cond.values()
                 if isinstance(v.get("temp_C"), dict) and "min" in v["temp_C"])
has_default = sum(1 for v in cond.values()
                  if isinstance(v.get("temp_C"), dict) and v["temp_C"].get("default") is not None)
print(f"  有 min/max 的: {has_minmax}/37   有 default 的: {has_default}/37")

print()
print("=" * 92)
print("② 溶剂名（37 类去重后的全部名字）")
print("=" * 92)
all_sol = Counter()
for v in cond.values():
    for s in (v.get("solvents") or []):
        all_sol[str(s)] += 1
print(f"  不同溶剂名 {len(all_sol)} 个，出现在 {sum(all_sol.values())} 个槽位")
print("  全部名字（按出现次数）:")
for s, n in all_sol.most_common():
    print(f"     {n:>3}  {s!r}")

print()
print("=" * 92)
print("③ 催化剂 / 试剂 / 碱")
print("=" * 92)
for field in ("catalysts", "reagents", "bases", "auxiliary_reagents"):
    c = Counter()
    for v in cond.values():
        for x in (v.get(field) or []):
            c[str(x)] += 1
    print(f"  {field}: {len(c)} 个不同值 -> {list(c)[:8]}")

print()
print("=" * 92)
print("④ n_ord_matched 分布（多少类真有数据）")
print("=" * 92)
ns = sorted((v.get("n_ord_matched", 0) for v in cond.values()), reverse=True)
print("  前 12:", ns[:12])
print("  后 8 :", ns[-8:])
print(f"  >=100 的: {sum(1 for n in ns if n>=100)}/37   >=10 的: {sum(1 for n in ns if n>=10)}/37")
