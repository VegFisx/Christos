# -*- coding: utf-8 -*-
r"""第十三轮（探针 4）：B 路候选（真实 PERCENTYIELD==0）的质量。

要回答：这些记录的"0% 收率"是【主产物 0%】（真反例），还是【某个副产物/中间体 0%】
（假反例 —— 主产物其实收率很高）？
口径：若同一条记录里所有 YIELD percentage 的最大值 == 0 -> "全零"（强候选）；
      否则 -> "有非零收率"（弱候选/需人工看）。

用法: python probe_yield_zero_quality.py [打印条数]
"""
import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
P = STAGE / "reports" / "negative_yield_zero.jsonl"
SHOW = int(sys.argv[1]) if len(sys.argv) > 1 else 5

recs = [json.loads(l) for l in P.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"B 路候选 {len(recs)} 条")
c = Counter()
allzero, mixed = [], []
for r in recs:
    vals = [y["value"] for y in r["all_yields"] if y["kind"] == "percentage"]
    if not vals:
        c["无百分比收率"] += 1
        continue
    if max(vals) == 0:
        c["全零（强候选）"] += 1
        allzero.append(r)
    else:
        c["有非零收率（弱候选）"] += 1
        mixed.append(r)
print()
for k, v in c.items():
    print(f"  {k:<20} {v}")
print()
print(f"  —— 全零样例（{min(SHOW, len(allzero))} 条）——")
for r in allzero[:SHOW]:
    print(f"  id={r['reaction_id']}  收率={r['real_percent_yield_zero']}")
    print(f"    notes: {r['notes_head'][:180]!r}")
    print(f"    CX: {(r['cxsmiles'] or '')[:140]}")
print()
print(f"  —— 有非零收率样例（{min(SHOW, len(mixed))} 条）——")
for r in mixed[:SHOW]:
    print(f"  id={r['reaction_id']}  各收率={[(y['details'], y['value']) for y in r['all_yields']][:4]}")
    print(f"    notes: {r['notes_head'][:140]!r}")
