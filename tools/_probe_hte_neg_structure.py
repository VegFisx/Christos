# -*- coding: utf-8 -*-
r"""一次性探针：hte_negatives.jsonl 的真实结构（只回答"我该信哪一列"）。

看：label 的取值分布、yield 分布、source 分布、溶剂取值、匹配到的短语分布。
"""
from __future__ import annotations

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
P = STAGE / "reports" / "hte_negatives.jsonl"

lab = Counter()
src = Counter()
solv = Counter()
matched = Counter()
n = 0
yields_zero = 0
yields_nonzero = 0
yvals = Counter()
examples_zero = []
with open(P, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        n += 1
        lab[str(r.get("label"))] += 1
        src[str(r.get("source"))] += 1
        solv[str(r.get("solvent"))] += 1
        for m in (r.get("matched") or []):
            matched[str(m)] += 1
        y = r.get("yield")
        if y is None:
            yvals["None"] += 1
        else:
            yvals[round(float(y), 1)] += 1
            if float(y) == 0.0:
                yields_zero += 1
                if len(examples_zero) < 2:
                    examples_zero.append({k: r.get(k) for k in
                                          ("source", "aryl", "amine", "product",
                                           "solvent", "temperature", "label",
                                           "matched")})
            else:
                yields_nonzero += 1

print(f"总行数 {n:,}")
print(f"label 分布: {dict(lab)}")
print(f"source 分布: {dict(src)}")
print(f"yield == 0.0: {yields_zero:,}   yield != 0.0: {yields_nonzero:,}")
print(f"yield 取值（前 10）: {yvals.most_common(10)}")
print(f"matched 短语（前 10）: {matched.most_common(10)}")
print(f"溶剂（前 12）: {solv.most_common(12)}")
print("\nyield==0 的两条完整样例：")
for e in examples_zero:
    for k, v in e.items():
        print(f"   {k:<12} = {str(v)[:100]}")
    print()
