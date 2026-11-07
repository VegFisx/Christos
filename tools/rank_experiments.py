#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""排序实验：在缓存的候选上离线比较排序公式（秒级，不再跑引擎）。

候选缓存由 `tools/collect_candidates.py` 生成。只重排、不重算候选，
所以 recall_any 完全一致，只有 top-1/5/10 与 MRR 变化。

第 97 轮（2026-11-04）加了两个维度：
  - ext：反应进程 extent（`conditions/extent.py`，0~1）——「跑到什么程度」
  - cur：curated 规则族（`rules/rules.json` 里的规则，相对 mined 模板）——「是不是有文献依据」

两个部分：
  1) 固定公式对照（engine / scorer / engine+cur / engine+ext ...）
  2) 五维权重网格：score = ws*scorer + we*发射序 + wu*support + wc*curated + wx*extent
     在调参半上挑最优，在验证半上报告（避免过拟合同一批数据）。

用法：
    python -I tools\\collect_candidates.py --n 3000 --out reports/cand_cache_3000.jsonl
    python -I tools\\rank_experiments.py --cache reports/cand_cache_3000.jsonl
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import scorer as S  # noqa: E402

RULE = {"priority": 0.5}


def sup01(n: int) -> float:
    v = S.support_score(n)
    return 0.0 if v is None else v


def prepared(cands):
    """预算每个候选的 (smi, scorer分, 发射序归一, support归一, curated, extent)。"""
    n = len(cands)
    out = []
    for i, c in enumerate(cands):
        sc, _d = S.score_product(c["smi"], RULE, c["act"], source_smiles=c["src"], support=0)
        em = 1.0 - (i / (n - 1) if n > 1 else 0.0)
        cu = float(c.get("cur", 0.0 if c["rule"].startswith("mined") else 1.0))
        out.append((c["smi"], sc, em, sup01(c["sup"]), cu, float(c.get("ext", 1.0))))
    return out


def rank_of(prep, want, weights):
    ws, we, wu, wc, wx = weights
    best = {}
    for smi, sc, em, su, cu, ex in prep:
        v = ws * sc + we * em + wu * su + wc * cu + wx * ex
        if smi not in best or v > best[smi]:
            best[smi] = v
    ordered = sorted(best.items(), key=lambda kv: -kv[1])
    return next((i + 1 for i, (smi, _) in enumerate(ordered) if smi == want), 0), len(best)


def metrics(ranks):
    n = max(1, len(ranks))
    return {
        "recall_any": round(sum(1 for r in ranks if r > 0) / n, 4),
        "top1": round(sum(1 for r in ranks if 0 < r <= 1) / n, 4),
        "top5": round(sum(1 for r in ranks if 0 < r <= 5) / n, 4),
        "top10": round(sum(1 for r in ranks if 0 < r <= 10) / n, 4),
        "mrr": round(sum(1.0 / r for r in ranks if r > 0) / n, 4),
    }


FIXED = {
    "engine":              (0.0, 1.0, 0.0, 0.0, 0.0),   # 纯发射序（当前生产）
    "scorer":              (1.0, 0.0, 0.0, 0.0, 0.0),   # 旧生产口径
    "scorer+sup":          (1.0, 0.0, 0.5, 0.0, 0.0),
    "engine+cur":          (0.0, 1.0, 0.0, 0.3, 0.0),
    "engine+ext":          (0.0, 1.0, 0.0, 0.0, 0.3),
    "engine+cur+ext":      (0.0, 1.0, 0.0, 0.2, 0.2),
    "ext_only":            (0.0, 0.0, 0.0, 0.0, 1.0),
    "cur_only":            (0.0, 0.0, 0.0, 1.0, 0.0),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / "reports" / "cand_cache_3000.jsonl"))
    a = ap.parse_args()

    t0 = time.time()
    recs = [json.loads(l) for l in Path(a.cache).open(encoding="utf-8")]
    prep = [(prepared(d["cands"]), d["want"]) for d in recs if d.get("cands")]
    print("缓存 %d 条 / %s" % (len(prep), a.cache))

    # 覆盖率：有多少候选带 extent / curated 信息（没有的话这俩维度就是白加）
    n_c = n_e = n_u = 0
    for pr, _w in prep:
        for (_smi, _sc, _em, _su, cu, ex) in pr:
            n_c += 1
            n_e += 1 if ex != 1.0 else 0
            n_u += 1 if cu > 0 else 0
    print("候选 %d 条：extent≠1.0 %d（%.1f%%）、curated %d（%.1f%%）"
          % (n_c, n_e, 100.0 * n_e / max(1, n_c), n_u, 100.0 * n_u / max(1, n_c)))

    fixed_out = {}
    for name, w in FIXED.items():
        ranks = [rank_of(pr, want, w)[0] for pr, want in prep]
        fixed_out[name] = metrics(ranks)
        m = fixed_out[name]
        print("%-16s top1 %.4f top5 %.4f top10 %.4f mrr %.4f"
              % (name, m["top1"], m["top5"], m["top10"], m["mrr"]))

    # 网格：调参半 → 验证半
    half = len(prep) // 2
    tune, valid = prep[:half], prep[half:]
    grid = []
    steps = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    for ws, we in itertools.product(steps, steps):
        if ws + we == 0 or ws + we > 1.0 + 1e-9:
            continue
        rest = 1.0 - ws - we
        for wu in (0.0, rest / 2, rest):
            for wc in (0.0, rest / 2, rest):
                wx = rest - wu - wc
                if wx < -1e-9:
                    continue
                grid.append((round(ws, 3), round(we, 3), round(wu, 3),
                             round(wc, 3), round(max(0.0, wx), 3)))
    best = None
    rows = []
    for w in grid:
        ranks = [rank_of(pr, want, w)[0] for pr, want in tune]
        m = metrics(ranks)
        rows.append((m, w))
        if best is None or (m["top1"], m["mrr"]) > (best[0]["top1"], best[0]["mrr"]):
            best = (m, w)
    rows.sort(key=lambda x: (-x[0]["top1"], -x[0]["mrr"]))
    print("\n网格 %d 组，调参半前 5：" % len(grid))
    for m, w in rows[:5]:
        print("  w=%s top1 %.4f top5 %.4f mrr %.4f" % (w, m["top1"], m["top5"], m["mrr"]))
    wr = best[1]
    vm = metrics([rank_of(pr, want, wr)[0] for pr, want in valid])
    print("选中权重 %s → 验证半 top1 %.4f top5 %.4f top10 %.4f mrr %.4f"
          % (wr, vm["top1"], vm["top5"], vm["top10"], vm["mrr"]))

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "cache": str(a.cache),
        "n": len(prep),
        "coverage": {"candidates": n_c, "extent_nondefault": n_e, "curated": n_u},
        "fixed_all": fixed_out,
        "grid_best_tune": {"weights": list(wr), "tune": best[0], "valid": vm},
        "grid_top5": [{"weights": list(w), "tune": m} for m, w in rows[:5]],
        "weights_meaning": "w=[scorer, 发射序, support, curated, extent]",
        "seconds": round(time.time() - t0, 1),
    }
    p = ROOT / "reports" / "rank_experiments_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s（%.1f s）" % (p, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
