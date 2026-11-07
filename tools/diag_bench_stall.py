# -*- coding: utf-8 -*-
"""定位宽档基准里「卡死」的那条反应（第 105 轮）。

背景：`paper_bench_50k_forward.py` 用宽档（mono=20000 + extra=60000 + cap128）
跑到第 46 批就不动了（7.5 小时无进展），怀疑某条反应在 RDKit/rdchiral 里爆炸。
做法：按 main() 完全相同的抽样逻辑重建 sample，对可疑批次逐条跑，
每条给一个子进程 + 超时，打印超时的那条的 id / class / 反应物 / 产物。

用法：
    python -I tools/diag_bench_stall.py --shard 0/8 --batch 45 --timeout 60
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "tools" / "paper_bench_50k_forward.py"


def load_bench():
    spec = importlib.util.spec_from_file_location("bench", str(BENCH))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 只是定义函数，不会执行 main
    return mod


def build_sample(mod, n_per: int, shard: str):
    by_cls = {}
    for line in open(mod.TARGETS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        by_cls.setdefault(str(r["class"]), []).append(r)
    rng = random.Random(mod.SEED)
    sample = []
    for c, lst in sorted(by_cls.items()):
        rng.shuffle(lst)
        sample.extend(lst[:min(n_per, len(lst))])
    sample.sort(key=lambda r: r["i"])
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        sample = [r for k, r in enumerate(sample) if k % sn == si]
    return sample


def child(rec: dict) -> None:
    """在子进程里跑一条反应；父进程负责超时。"""
    sys.path.insert(0, str(ROOT / "core"))
    sys.path.insert(0, str(ROOT / "conditions"))
    sys.path.insert(0, str(ROOT))
    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    eng = SmartReactEngine(extra_template_min_support=1, extra_template_limit=60000,
                           mono_template_limit=20000, mono_include_co_reagent=True,
                           max_products_per_pair=128)
    comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
             for j, s in enumerate(rec["reactants"])]
    t = time.time()
    prods = eng.step(comps, T.get_template("煎煮"), round_no=1)
    print("OK %s %.1fs n=%d" % (rec["i"], time.time() - t, len(prods)), flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="0/8")
    ap.add_argument("--batch", type=int, default=45)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--limit", type=int, default=60)
    a = ap.parse_args()

    mod = load_bench()
    sample = build_sample(mod, 100000, a.shard)
    lo = a.batch * 60
    part = sample[lo:lo + a.limit]
    print("shard %s：样本 %d 条，检查第 %d 批（%d 条）" % (a.shard, len(sample), a.batch, len(part)))

    ctx = mp.get_context("spawn")
    for rec in part:
        p = ctx.Process(target=child, args=(rec,), daemon=True)
        t0 = time.time()
        p.start()
        p.join(a.timeout)
        if p.is_alive():
            p.terminate()
            p.join(5)
            print("TIMEOUT id=%s class=%s dt=%.0fs" % (rec["i"], rec["class"], time.time() - t0))
            print("  reactants=%s" % (rec["reactants"],))
            print("  product=%s" % rec["product"])
            return 2
        print("done %s class=%s %.1fs" % (rec["i"], rec["class"], time.time() - t0), flush=True)
    print("这批没有超时")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
