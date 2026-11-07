#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A：把「候选集合命中率」升级成「排序准确率」。

92.01% 是「真产物出现在候选里」（平均 21.5 个候选）。用同一批反应再算三个更硬的数：

  * top-1 / top-5 / top-10 准确率：按 `Product.score` 排序后，真产物落在第几位；
  * 平均候选数、平均正确候选的分数位次（MRR）；
  * 误报规模：每条反应给出的候选里有多少是错的（precision 的分母）。

用法：
    python -I tools\\bench_topk.py [--n 3000] [--seed 20261014]
输出：reports/bench_topk_20261104.json
"""
from __future__ import annotations

import argparse
import ast
import json
import statistics
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = ROOT / "reports" / "bench_topk_20261104.json"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--no-support", action="store_true", dest="no_support",
                    help="不把模板支持度当先验（复现第 94 轮的排序基线）")
    ap.add_argument("--by-score", action="store_true", dest="by_score",
                    help="按 scorer 分数排序（旧口径），默认按引擎发射序")
    ap.add_argument("--mined-wide", action="store_true", dest="mined_wide",
                    help="放宽 mined 模板装载（min_support=1, extra limit 60000, "
                         "mono limit 60000 + 共底物）——第 100 轮的权衡实验")
    ap.add_argument("--maxprod", type=int, default=0,
                    help="每对产物上限（0=用引擎默认）")
    ap.add_argument("--extent-gate", action="store_true", dest="extent_gate",
                    help="第 101 轮：打开「条件→反应进程」门（温度/时间/pH/催化剂），"
                         "e<extent_min 的产物不产出")
    a = ap.parse_args()

    import random
    import scorer as S
    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    rows = []
    with TESTSET.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    random.Random(a.seed).shuffle(rows)
    picked = rows[: a.n]

    t0 = time.time()
    if a.mined_wide:
        eng = SE.SmartReactEngine(extra_template_min_support=1,
                                  extra_template_limit=60000,
                                  mono_template_limit=60000,
                                  mono_include_co_reagent=True)
    else:
        eng = SE.SmartReactEngine()
    if a.maxprod:
        eng.max_products_per_pair = a.maxprod
    cond = T.get_template("煎煮")

    ranks = []
    n_eval = n_err = 0
    cand_counts = []
    for d in picked:
        rl = d["reactants"]
        rl = ast.literal_eval(rl) if isinstance(rl, str) else rl
        comps = []
        bad = False
        for i, smi in enumerate(rl[:2]):
            if Chem.MolFromSmiles(smi) is None:
                bad = True
                break
            comps.append(Compound(smiles=smi, name="R%d" % i, herb="(bench)"))
        if bad or not comps:
            continue
        want = canon(d.get("product") or "")
        if not want:
            continue
        try:
            prods = eng.step(comps, cond, round_no=1, extent_gate=a.extent_gate)
        except Exception:
            n_err += 1
            continue
        n_eval += 1
        # 第96轮：默认按**引擎发射序**排序（= 生产台账现在的展示顺序）。
        # 实测 3,000 条：发射序 top-1 42.71% / MRR 0.547，scorer 只有 32.50% / 0.442。
        # --by-score 走旧的 scorer 排序，保留作对照。
        first = {}
        scored = {}
        for p in prods:
            cs = canon(getattr(p, "smiles", "") or "")
            if not cs:
                continue
            sq = int(getattr(p, "seq", 0) or 0)
            if cs not in first or (sq and sq < first[cs]):
                first[cs] = sq
            if a.by_score:
                rule = eng._rule_by_id.get(getattr(p, "rule_id", ""), {}) or {}
                sup = 0 if a.no_support else int(getattr(p, "template_support", 0) or 0)
                try:
                    sc, _d = S.score_product(cs, rule, float(getattr(p, "activation", 0.0) or 0.0),
                                             source_smiles=getattr(p, "source_smiles", "") or "",
                                             support=sup)
                except Exception:
                    sc = float(getattr(p, "score", 0.0) or 0.0)
                if cs not in scored or sc > scored[cs]:
                    scored[cs] = sc
        cand_counts.append(len(first))
        ordered = ([c for c in sorted(scored.items(), key=lambda kv: -kv[1])]
                   if a.by_score else
                   [(cs, sq) for cs, sq in sorted(first.items(), key=lambda kv: kv[1])])
        rank = next((i + 1 for i, (smi, _) in enumerate(ordered) if smi == want), 0)
        ranks.append(rank)   # 0 = 没命中

    def acc(k):
        return round(sum(1 for r in ranks if 0 < r <= k) / max(1, n_eval), 4)

    hit = sum(1 for r in ranks if r > 0)
    mrr = round(sum(1.0 / r for r in ranks if r > 0) / max(1, n_eval), 4)
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_requested": a.n,
        "n_evaluated": n_eval,
        "n_engine_errors": n_err,
        "recall_any": round(hit / max(1, n_eval), 4),
        "top1": acc(1), "top5": acc(5), "top10": acc(10),
        "mrr": mrr,
        "candidates": {
            "mean": round(statistics.mean(cand_counts), 1) if cand_counts else None,
            "median": statistics.median(cand_counts) if cand_counts else None,
            "p90": sorted(cand_counts)[int(len(cand_counts) * 0.9)] if cand_counts else None,
        },
        "hit_rank": {
            "median": statistics.median([r for r in ranks if r > 0]) if hit else None,
            "share_rank1": acc(1),
        },
        "seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
