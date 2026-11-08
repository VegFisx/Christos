#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""候选规模与 top-k 曲线：回答「是排不出来，还是根本不在候选里」。

用法：
    python -I tools\\rank_curves.py --data reports/cand_cache_3000.jsonl \\
        --out reports/rank_curves_20261107.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
KS = [1, 2, 3, 5, 10, 20, 32, 50, 100]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "reports" / "cand_cache_3000.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "rank_curves_20261107.json"))
    a = ap.parse_args()

    rows = [json.loads(l) for l in Path(a.data).open(encoding="utf-8")]
    n = len(rows)
    hit_pos = []          # 1-based 位置；0 表示不在候选里
    sizes = []
    for d in rows:
        want = d["want"]
        cands = d.get("cands") or []
        sizes.append(len(cands))
        pos = 0
        for i, c in enumerate(cands, 1):
            if c.get("smi") == want:
                pos = i
                break
        hit_pos.append(pos)

    in_cand = sum(1 for p in hit_pos if p > 0)
    curve = {}
    for k in KS:
        curve[str(k)] = round(sum(1 for p in hit_pos if 0 < p <= k) / max(1, n), 4)
    miss_rank = [p for p in hit_pos if p > 0]
    res = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "data": str(a.data),
        "n_reactions": n,
        "in_candidate_recall": round(in_cand / max(1, n), 4),
        "not_in_candidates": n - in_cand,
        "topk_recall": curve,
        "candidate_count": {
            "mean": round(sum(sizes) / max(1, n), 2),
            "median": sorted(sizes)[len(sizes) // 2] if sizes else 0,
            "p90": sorted(sizes)[int(0.9 * (len(sizes) - 1))] if sizes else 0,
            "max": max(sizes) if sizes else 0,
        },
        "hit_rank": {
            "median": sorted(miss_rank)[len(miss_rank) // 2] if miss_rank else None,
            "p90": sorted(miss_rank)[int(0.9 * (len(miss_rank) - 1))] if miss_rank else None,
        },
        "note": "候选为引擎默认档（cap 32）单轮输出，按发射序；in_candidate_recall 是候选上限，"
                "top-1 到 in_candidate_recall 之间的差距全部来自排序。",
    }
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_reactions", "in_candidate_recall", "topk_recall", "candidate_count", "hit_rank")},
                     ensure_ascii=False, indent=1))
    print("写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
