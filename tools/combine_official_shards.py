# -*- coding: utf-8 -*-
"""把分片跑出来的 official bench 结果合并成一份（逐条 JSONL 为准，不用四舍五入的汇总）。

用法：
  python -I tools\\combine_official_shards.py --prefix full5_rs2 --n-shards 5
  python -I tools\\combine_official_shards.py --tags a,b,c --out reports\\paper\\results\\x.json

为什么需要：`paper_bench_official_test.py` 每片各写一个 json/jsonl；分片跑是为了
避免一次长跑被系统回收后全部白跑。合并时必须校验：
  1. 五片的 reaction id 恰好覆盖 0..N-1，无重复、无缺口；
  2. 五片的配置除 SHARD/TAG 外一致。
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

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "reports" / "paper" / "results"
IGNORE_CFG = {"CHEMCREACT_BENCH_SHARD", "CHEMCREACT_BENCH_TAG"}


def _load(tag: str):
    js = RESULTS / ("forward_official_test__%s.json" % tag)
    jl = RESULTS / ("forward_official_test__%s.jsonl" % tag)
    if not js.is_file() or not jl.is_file():
        raise FileNotFoundError("缺结果文件：%s / %s" % (js.name, jl.name))
    summary = json.loads(js.read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in jl.read_text(encoding="utf-8").splitlines() if x.strip()]
    return summary, rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="full5_rs2")
    ap.add_argument("--n-shards", type=int, default=5)
    ap.add_argument("--tags", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    tags = ([t.strip() for t in a.tags.split(",") if t.strip()]
            if a.tags else ["%s_s%d" % (a.prefix, i) for i in range(a.n_shards)])

    summaries, rows_all, cfgs = [], [], []
    for t in tags:
        s, rows = _load(t)
        summaries.append(s)
        rows_all.extend(rows)
        cfgs.append({k: v for k, v in (s.get("config_env") or {}).items()
                     if k not in IGNORE_CFG})

    # 1) 覆盖校验：分片是按位置切的，id 是原始 CSV 行号（跳过的坏行会让 id 不连续），
    #    所以不能拿 range(n) 比；只校验「总数对得上 + 无重复」。
    ids = [r["i"] for r in rows_all]
    n_expected = sum(s["n_reactions"] for s in summaries)
    dup = len(ids) - len(set(ids))
    if dup or len(ids) != n_expected:
        print("[FAIL] 分片覆盖不对：总数 %d（应为 %d），去重 %d，重复 %d"
              % (len(ids), n_expected, len(set(ids)), dup))
        return 1
    # 2) 配置一致性
    if any(c != cfgs[0] for c in cfgs[1:]):
        print("[FAIL] 各片配置不一致：")
        for t, c in zip(tags, cfgs):
            print("  %s %s" % (t, c))
        return 1

    ok = [r for r in rows_all if "error" not in r]
    err = [r for r in rows_all if "error" in r]
    n = len(ok)
    hits = sum(1 for r in ok if r["hit"])
    ranks = [r["rank"] for r in ok if r["hit"]]
    mean_cand = sum(r["n_products"] for r in ok) / max(1, n)
    by_class: dict = {}
    for r in ok:
        d = by_class.setdefault(str(r["class"]), {"n": 0, "hit": 0})
        d["n"] += 1
        d["hit"] += 1 if r["hit"] else 0

    def topk(k: int) -> float:
        return round(sum(1 for x in ranks if x <= k) / max(1, n), 4)

    combined = {
        "generated_at": summaries[0].get("generated_at", ""),
        "source": summaries[0].get("source", ""),
        "tags": tags,
        "n_reactions": n_expected,
        "n_scored": n,
        "n_errors": len(err),
        "recall_1step": round(hits / max(1, n), 4),
        "top1": topk(1), "top3": topk(3), "top5": topk(5), "top10": topk(10),
        "mrr": round(sum(1.0 / x for x in ranks) / max(1, n), 4),
        "candidate_stats": {"mean": round(mean_cand, 2)},
        "by_class_recall": {c: {"n": d["n"], "rate": round(d["hit"] / d["n"], 4)}
                            for c, d in sorted(by_class.items())},
        "seconds": round(sum(float(s.get("seconds") or 0) for s in summaries), 1),
        "config_env": summaries[0].get("config_env") or {},
        "per_shard": [{"tag": t, "n": s["n_reactions"], "recall": s["recall_1step"],
                       "top1": s["top1"], "mean_cand": (s.get("candidate_stats") or {}).get("mean")}
                      for t, s in zip(tags, summaries)],
    }
    out = Path(a.out) if a.out else RESULTS / ("forward_official_test__%s.json" % a.prefix)
    out.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")
    print("合并 %d 片 -> %d 条（错误 %d）" % (len(tags), n, len(err)))
    print("命中 %d/%d = %.2f%%  top1 %.2f%%  top5 %.2f%%  MRR %.4f  平均候选 %.2f"
          % (hits, n, 100.0 * hits / max(1, n), 100 * combined["top1"],
             100 * combined["top5"], combined["mrr"], mean_cand))
    for t, s in zip(tags, summaries):
        print("  %-18s n=%-4d recall %.2f%%  top1 %.2f%%  候选 %.1f"
              % (t, s["n_reactions"], 100 * s["recall_1step"], 100 * s["top1"],
                 (s.get("candidate_stats") or {}).get("mean", float("nan"))))
    print("写出", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
