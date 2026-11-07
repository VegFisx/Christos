# -*- coding: utf-8 -*-
r"""第十二轮（探针）：覆盖率表里到底存了什么 —— 有没有被 CXSMILES 拆碎的离子碎片。

背景：CXSMILES 的反应物按 "." 拆分，K2CO3 -> "O=C([O-])[O-]" + "[K+]" 两个"反应物"，
      于是覆盖率把 [K+]/[Na+] 当成独立辅助试剂统计。
本探针把若干关键类的 required + optional 原样打出来，供决定判据怎么修。

用法: python probe_coverage_entries.py [类名...]
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
D = json.loads((STAGE / "reports" / "aux_reagent_coverage.json").read_text(encoding="utf-8"))

KEYS = sys.argv[1:] or ["mitsunobu", "suzuki", "amide_coupling",
                        "reductive_amination_aldehyde", "reductive_amination_ketone",
                        "williamson", "ester_sulfonic_schotten_baum", "esterification"]
for k in KEYS:
    e = D.get(k)
    if not e:
        print(f"{k}: <不在表里>")
        continue
    print(f"{k}  n={e['n_reactions']}")
    for tag in ("required", "optional"):
        items = e.get(tag) or []
        print(f"  {tag}: {[(i['smiles'], i['coverage']) for i in items]}")
    print()

print("--- 全表里出现过的「单原子/离子」碎片（可能都是反离子） ---")
ions = {}
for k, e in D.items():
    for tag in ("required", "optional"):
        for i in e.get(tag) or []:
            s = i["smiles"]
            if len(s) <= 5 and "[" in s:
                ions.setdefault(s, []).append((k, tag, i["coverage"]))
for s, uses in sorted(ions.items(), key=lambda x: -len(x[1])):
    print(f"  {s:<8} 出现在 {len(uses)} 处: {uses[:4]}")
