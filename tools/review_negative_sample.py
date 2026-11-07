# -*- coding: utf-8 -*-
r"""第十三轮：反例候选的【人工复核抽样】—— 打印原文，由人判真伪。

449 条文本候选是"正则命中"，不是"已验证的反例"。本脚本用固定种子抽 N 条，
把命中上下文原样打出来，供人逐条判：真反例 / 假阳性（噪声）/ 说不清。
判完把数字写进报告 —— 这是【实测精度】，不是推断。

用法: python review_negative_sample.py [N] [seed]
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
JSONL = STAGE / "reports" / "negative_examples.jsonl"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20261011

recs = [json.loads(l) for l in JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
random.seed(SEED)
sample = random.sample(recs, min(N, len(recs)))
print("=" * 96)
print(f"反例候选人工复核抽样：从 {len(recs)} 条里抽 {len(sample)} 条（seed={SEED}）")
print("=" * 96)
for i, r in enumerate(sample, 1):
    print(f"[{i}] {r['reaction_id']}  短语={r['matched']}")
    print(f"    温度={r.get('temperature')}")
    for c in r["contexts"][:2]:
        print(f"    <{c['pattern']}> …{c['context']}…")
    print(f"    notes头: {r['notes_head'][:160]!r}")
    print()
print("=" * 96)
print("按短语统计（抽样内）:")
for tag, n in Counter(t for r in sample for t in r["matched"]).most_common():
    print(f"  {tag:<26} {n}")
