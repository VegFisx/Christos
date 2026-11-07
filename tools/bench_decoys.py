#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""假阳性（诱饵对）测试：给引擎喂「不该发生的搭配」，看它是不是也说能反应。

为什么这么测：测试集每个反应只有一个登记产物，所以「引擎多给的候选」到底是不是
错的，没有现成的答案（没被登记 ≠ 错）。可行的替代是**特异性**：
拿两个本来不在同一个反应里的分子凑一对，如果引擎照样吐一堆产物，
就说明它对「该不该反应」没有辨别力——这是假阳性的上界估计。

注意口径：诱饵对里确实可能存在真反应（两个都是活性分子），所以
「诱饵命中率」是**上界**，不是精确 FPR；相对比较（真反应对 vs 诱饵对）才有意义。

用法：
    python -I tools\\bench_decoys.py --n 500
"""
from __future__ import annotations

import argparse
import ast
import json
import random
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


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def run_pairs(pairs, cond, n_limit=None):
    """跑一批 (smi_a, smi_b)，返回每条产物数。"""
    import smartreact_engine as SE
    from engine import Compound

    eng = SE.SmartReactEngine()
    counts, errs = [], 0
    for i, (a, b) in enumerate(pairs):
        if n_limit is not None and i >= n_limit:
            break
        comps = [Compound(smiles=a, name="A", herb="(decoy)"),
                 Compound(smiles=b, name="B", herb="(decoy)")]
        try:
            prods = eng.step(comps, cond, round_no=1)
            counts.append(len(prods))
        except Exception:          # noqa: BLE001 —— 计数，不静默
            errs += 1
            counts.append(0)
    return counts, errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=500, help="诱饵对数量（也是真反应对的对比数量）")
    ap.add_argument("--seed", type=int, default=20261014)
    a = ap.parse_args()

    import templates as T

    cond = T.get_template("煎煮")
    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    rnd = random.Random(a.seed)
    rnd.shuffle(rows)
    t0 = time.time()

    # 真反应对：取前 n 条反应的两个反应物
    real_pairs, real_rows = [], []
    for d in rows:
        rl = ast.literal_eval(d["reactants"]) if isinstance(d["reactants"], str) else d["reactants"]
        rl = [canon(s) for s in rl[:2]]
        rl = [s for s in rl if s]
        if len(rl) == 2:
            real_pairs.append((rl[0], rl[1]))
            real_rows.append(d)
        if len(real_pairs) >= a.n:
            break
    real_counts, real_err = run_pairs(real_pairs, cond)
    print("真反应对 %d 条，%.1f s" % (len(real_counts), time.time() - t0))

    # 诱饵对：把真反应对的两个反应物**拆开重配**——A 来自第 i 条、B 来自第 i+k 条
    pool = [p[0] for p in real_pairs] + [p[1] for p in real_pairs]
    pool = [s for s in dict.fromkeys(pool) if s]
    decoys, used = [], set()
    guard = 0
    while len(decoys) < a.n and guard < a.n * 50:
        guard += 1
        x, y = rnd.sample(pool, 2)
        key = tuple(sorted((x, y)))
        if key in used:
            continue
        used.add(key)
        decoys.append((x, y))
    t1 = time.time()
    decoy_counts, decoy_err = run_pairs(decoys, cond)
    print("诱饵对 %d 条，%.1f s" % (len(decoy_counts), time.time() - t1))

    def summ(counts):
        n = max(1, len(counts))
        return {
            "n": len(counts),
            "hit_rate": round(sum(1 for c in counts if c > 0) / n, 4),
            "mean_products": round(sum(counts) / n, 2),
            "median_products": statistics.median(counts) if counts else 0,
            "p90_products": sorted(counts)[int(len(counts) * 0.9)] if counts else 0,
            "zero_rate": round(sum(1 for c in counts if c == 0) / n, 4),
        }

    real, decoy = summ(real_counts), summ(decoy_counts)
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "condition": "煎煮",
        "seed": a.seed,
        "real_pairs": real,
        "decoy_pairs": decoy,
        "errors": {"real": real_err, "decoy": decoy_err},
        "specificity_estimate": round(1.0 - decoy["hit_rate"], 4),
        "note": ("诱饵对 = 把真反应的 A、B 两个反应物拆开重配。hit_rate 是假阳性上界："
                 "两个活性分子凑一起确实可能真反应，所以 specificity_estimate 偏保守偏低。"),
        "seconds": round(time.time() - t0, 1),
    }
    p = ROOT / "reports" / "decoy_test_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
