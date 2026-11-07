# -*- coding: utf-8 -*-
r"""第十三轮：把待复核的反例候选切成 N 块，供并行逐条标注。

输入: reports/neg_screened_strict.jsonl (A 路) + reports/neg_screened_b_zero.jsonl (B 路)
输出: reports/neg_chunks/chunk_{k}.jsonl（含 source 字段标明来自哪条路线）

用法: python make_review_chunks.py [块数，默认 6]
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
OUTDIR = STAGE / "reports" / "neg_chunks"
N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 6


def load(p, source):
    recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in recs:
        r["source"] = source
    return recs


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "--v2":
        # ★ 只切【B-v2 里还没复核过】的：B 路 404 条里 379 条是伪影，
        #   v2 硬过滤（0% 必须挂在有结构标识符的产物上）剩 25 条，其中 17 条未复核。
        R = STAGE / "reports"
        v2 = load(R / "negative_yield_zero_v2.jsonl", "B_yield0_v2")
        reviewed = set()
        for name in ("neg_screened_b_zero.jsonl", "neg_screened_strict.jsonl"):
            reviewed |= {r["reaction_id"] for r in load(R / name, "x")}
        recs = [r for r in v2 if r["reaction_id"] not in reviewed]
        p = OUTDIR / "chunk_v2.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  {p.name}: {len(recs)} 条（B-v2 共 {len(v2)} 条，已复核 {len(v2)-len(recs)} 条）")
        return 0

    recs = load(STAGE / "reports" / "neg_screened_strict.jsonl", "A_text") + \
        load(STAGE / "reports" / "neg_screened_b_zero.jsonl", "B_yield0")
    # 交错分配，保证每块都有 A 和 B
    chunks = [[] for _ in range(N)]
    for i, r in enumerate(recs):
        chunks[i % N].append(r)
    for k, ch in enumerate(chunks):
        p = OUTDIR / f"chunk_{k}.jsonl"
        with open(p, "w", encoding="utf-8") as f:
            for r in ch:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        na = sum(1 for r in ch if r["source"] == "A_text")
        print(f"  {p.name}: {len(ch)} 条 (A {na} / B {len(ch)-na})")
    print(f"共 {len(recs)} 条 -> {N} 块，目录 {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
