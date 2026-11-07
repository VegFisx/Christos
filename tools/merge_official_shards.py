"""合并多分片的 official-test 结果（MIT 480K 抽样 / 官方 50K 切分通用）。

用法:
    python -I tools/merge_official_shards.py --dir reports/paper/results/mit480k_20261106 \
        --tags mit_s0 mit_s1 mit_s2 mit_s3 --out reports/paper/results/mit480k_20261106/merged.json

输入每片: forward_official_test__<TAG>.jsonl（逐条 {"i","class","hit","rank","n_products"}）
输出: 合并 json（去重按 i），含 recall/top-k/mrr/候选统计/类别表。
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    d = Path(args.dir)
    rows: dict[int, dict] = {}
    files = []
    for tag in args.tags:
        f = d / f"forward_official_test__{tag}.jsonl"
        if not f.exists():
            print(f"[warn] 缺片: {f}")
            continue
        files.append(f.name)
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                o = json.loads(line)
                rows[int(o["i"])] = o

    n = len(rows)
    if not n:
        print("没有数据")
        return 1

    hit = sum(1 for o in rows.values() if o.get("hit"))
    ranks = [o["rank"] for o in rows.values() if o.get("hit") and o.get("rank")]
    cands = [o.get("n_products", 0) for o in rows.values()]
    by_cls = defaultdict(list)
    for o in rows.values():
        by_cls[str(o.get("class", "?"))].append(bool(o.get("hit")))

    def topk(k: int) -> float:
        return sum(1 for r in ranks if r <= k) / n

    mrr = sum(1.0 / r for r in ranks) / n
    out = {
        "n_reactions": n,
        "files": files,
        "recall_1step": hit / n,
        "top1": topk(1),
        "top3": topk(3),
        "top5": topk(5),
        "top10": topk(10),
        "mrr": mrr,
        "candidate_stats": {
            "mean": statistics.fmean(cands),
            "median": statistics.median(cands),
            "p90": sorted(cands)[int(0.9 * (n - 1))],
        },
        "by_class_recall": {
            k: {"n": len(v), "rate": sum(v) / len(v)} for k, v in sorted(by_cls.items())
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print("写出", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
