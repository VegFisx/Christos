#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""第 101 轮：条件灵敏度基准（条件到底有没有真的改变产物集合）。

口径（写死）：
  * 样本：reports/paper/data/uspto50k_canon.jsonl 里按 seed 抽 N 条反应，
    用记录的**反应物**当输入（与 paper_bench_50k_forward 同源、同口径）。
  * 同一批输入，依次在 K 个条件预设下跑 1 轮，收集规范化产物集合。
  * 指标：
      - 每个预设相对「煎煮」的 Jaccard（交集/并集）—— 1.0 = 完全没差别；
      - 每个预设相对「煎煮」的独有产物数（只在该预设出现）；
      - 判零反应数（产物集合为空）；
      - 与条件无关的对照：同预设跑两遍的 Jaccard 应为 1.0。
  * 本基准只看**集合差异**，不看对错——对错由 50k 召回基准负责。

用法：
    python -I tools\\bench_condition_sensitivity.py [--n 60] [--cond-extent 1|0]
输出：reports/bench_condition_sensitivity_<tag>.json
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
PRESETS = ["煎煮", "炮制·醋炙", "炮制·盐炙", "炮制·姜炙", "炮制·炒炭",
           "炮制·酒炙", "酸水解", "碱水解", "室温浸泡"]


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--cond-extent", type=int, default=1, dest="cond_extent",
                    help="1=条件进程门开（默认），0=关（旧行为）")
    ap.add_argument("--base", default="煎煮", help="对照预设")
    a = ap.parse_args()

    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    rows = []
    with TESTSET.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    random.Random(a.seed).shuffle(rows)

    picked = []
    for r in rows:
        rl = r["reactants"]
        rl = ast.literal_eval(rl) if isinstance(rl, str) else rl
        if not rl or len(rl) > 3:
            continue
        if any(Chem.MolFromSmiles(s) is None for s in rl):
            continue
        picked.append([canon(s) for s in rl])
        if len(picked) >= a.n:
            break

    t0 = time.time()
    eng = SE.SmartReactEngine(condition_extent=bool(a.cond_extent))
    print("引擎就绪（%.1fs）；样本 %d 条" % (time.time() - t0, len(picked)), flush=True)

    sets = {name: [] for name in PRESETS}
    n_err = 0
    for k, rl in enumerate(picked, 1):
        comps = [Compound(smiles=s, name="R%d" % i, herb="(bench)") for i, s in enumerate(rl)]
        for name in PRESETS:
            cond = T.get_template(name)
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception as ex:              # noqa: BLE001 —— 计数并打印，不静默
                n_err += 1
                print("   [err] %s / %s: %s" % (name, type(ex).__name__, ex))
                continue
            sets[name].append({canon(getattr(p, "smiles", "") or "") for p in prods} - {""})
        if k % 10 == 0:
            print("   ... %d/%d（%.0fs）" % (k, len(picked), time.time() - t0), flush=True)

    base = sets[a.base]
    out = {"n": len(picked), "seed": a.seed, "cond_extent": a.cond_extent,
           "n_errors": n_err, "presets": {}, "seconds": round(time.time() - t0, 1)}

    def jac(x, y):
        u = x | y
        return len(x & y) / len(u) if u else 1.0

    for name in PRESETS:
        cur = sets[name]
        if not cur:
            continue
        js = [jac(b, c) for b, c in zip(base, cur)]
        uniq = [len(c - b) for b, c in zip(base, cur)]
        out["presets"][name] = {
            "jaccard_vs_base_mean": round(statistics.mean(js), 4),
            "jaccard_vs_base_median": round(statistics.median(js), 4),
            "share_identical": round(sum(1 for j in js if j >= 0.999) / len(js), 4),
            "unique_products_mean": round(statistics.mean(uniq), 2),
            "empty_share": round(sum(1 for c in cur if not c) / len(cur), 4),
            "mean_products": round(statistics.mean(len(c) for c in cur), 2),
        }

    tag = "extent_on" if a.cond_extent else "extent_off"
    dst = ROOT / "reports" / ("bench_condition_sensitivity_%s.json" % tag)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=" * 78)
    print("%-14s %8s %8s %10s %10s %8s" %
          ("预设", "Jaccard", "完全相同", "独有产物", "平均产物", "空集"))
    for name, v in out["presets"].items():
        print("%-14s %8.3f %8.1f%% %10.2f %10.2f %7.1f%%" %
              (name, v["jaccard_vs_base_mean"], 100 * v["share_identical"],
               v["unique_products_mean"], v["mean_products"], 100 * v["empty_share"]))
    print("耗时 %.0fs；错误 %d" % (time.time() - t0, n_err))
    print("-> %s" % dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
