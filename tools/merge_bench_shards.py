# -*- coding: utf-8 -*-
"""合并分片基准结果并重算汇总（第 105 轮）。

用法:
    python -I tools/merge_bench_shards.py --tag wide128m20k --out reports/paper/results/wide128_mono20k_round105

读取 `forward_per_reaction__<tag>_s*.jsonl`（分片产物），按与
`tools/paper_bench_50k_forward.py` 完全相同的口径重算汇总，写出
`forward_50k__<tag>.json` 与 `forward_per_reaction__<tag>.jsonl`。
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cond", default="煎煮")
    a = ap.parse_args()

    out = Path(a.out)
    files = sorted(glob.glob(str(out / ("forward_per_reaction__%s_s*.jsonl" % a.tag))))
    if not files:
        print("没有分片文件：" + str(out / ("forward_per_reaction__%s_s*.jsonl" % a.tag)))
        return 1
    rows = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    # 去重（同一条反应可能出现在多片，正常不该发生）
    seen = {}
    for r in rows:
        seen[r.get("i", -1)] = r
    rows = [seen[k] for k in sorted(seen)]
    ok = [r for r in rows if "error" not in r]
    n = len(ok)
    hits = sum(1 for r in ok if r["hit"])
    nprod = [r["n_products"] for r in ok]
    by_cls = {}
    for r in ok:
        d = by_cls.setdefault(str(r["class"]), {"n": 0, "hit": 0})
        d["n"] += 1
        d["hit"] += 1 if r["hit"] else 0
    excl = [r for r in ok if r.get("in_sources")]
    summary = {
        "n_reactions": n,
        "n_shards": len(files),
        "seed": 20261014,
        "cond": a.cond,
        "rounds": 1,
        "recall_1step": round(hits / max(1, n), 4),
        "n_errors": len(rows) - n,
        "candidate_stats": {
            "mean": round(sum(nprod) / max(1, n), 1),
            "median": sorted(nprod)[len(nprod) // 2] if nprod else 0,
            "p90": sorted(nprod)[int(0.9 * len(nprod))] if nprod else 0,
            "zero_share": round(sum(1 for x in nprod if x == 0) / max(1, n), 4),
        },
        "by_class_recall": {c: {"n": d["n"], "rate": round(d["hit"] / max(1, d["n"]), 4)}
                            for c, d in sorted(by_cls.items())},
        "in_sources_subset": {"n": len(excl),
                              "recall": round(sum(1 for r in excl if r["hit"]) / max(1, len(excl)), 4)},
        "merged_from": [Path(f).name for f in files],
    }
    (out / ("forward_50k__%s.json" % a.tag)).write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(out / ("forward_per_reaction__%s.jsonl" % a.tag), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("合并 %d 片 / %d 条" % (len(files), n))
    print("召回 %d/%d = %.2f%%" % (hits, n, 100.0 * hits / max(1, n)))
    print("候选：均值 %.1f / 中位 %d / p90 %d / 空集 %.2f%%" % (
        summary["candidate_stats"]["mean"], summary["candidate_stats"]["median"],
        summary["candidate_stats"]["p90"], 100 * summary["candidate_stats"]["zero_share"]))
    for c, d in sorted(by_cls.items()):
        print("  类 %-3s n=%-6d %.2f%%" % (c, d["n"], 100.0 * d["hit"] / max(1, d["n"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
