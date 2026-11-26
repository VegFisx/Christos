# -*- coding: utf-8 -*-
"""缺失反应归因：产物是被过滤掉了，还是模板根本没装载，还是真的没有模板。

对每条缺失反应：
  1. 生产配置跑一遍，开 debug_drops —— 若真产物被 classify / cap 丢弃 → 「过滤」
  2. 放宽配置（模板全装、cap 256、预筛/门控关）再跑 → 出现真产物 → 「模板没装载」
  3. 两者都不出现 → 「真缺口」

用法：
  python tools\\diagnose_miss_reachability.py            # 100 条
  python tools\\diagnose_miss_reachability.py --n 50
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import candidate_table as CT  # noqa: E402


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--table", default=str(CT.DEFAULT_DIR / "candidates_cli.parquet"))
    ap.add_argument("--meta", default=str(CT.DEFAULT_DIR / "meta_cli.json"))
    a = ap.parse_args()

    df, meta = CT.load(parquet=a.table, meta=CT.load_meta(a.meta),
                       columns=["rid", "want", "n_pos", "r1", "r2"])
    rxn = df.groupby("rid", sort=False).first().reset_index()
    miss = rxn[rxn["n_pos"] == 0].reset_index(drop=True)
    if len(miss) == 0:
        print("没有缺失反应")
        return 0
    step = max(1, len(miss) // a.n)
    sample = miss.iloc[::step].head(a.n).reset_index(drop=True)
    print("缺失 %d 条，抽样 %d 条（每 %d 条取 1）" % (len(miss), len(sample), step))

    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    cond = T.get_template("煎煮")
    t0 = time.time()
    print("加载生产配置引擎 ...", flush=True)
    prod = SE.SmartReactEngine(use_curated_templates=True, strict_redox_gate=True,
                               use_mined_top_conditions=True)
    prod.debug_drops = None
    print("加载放宽配置引擎（模板全装）...", flush=True)
    relax = SE.SmartReactEngine(use_curated_templates=True, strict_redox_gate=False,
                                use_mined_top_conditions=True,
                                extra_template_min_support=1, extra_template_limit=50000,
                                mono_template_limit=50000,
                                max_products_per_pair=256, max_pairs=20000,
                                prefilter=False, gate_conditions=False)
    print("引擎就绪 %.0f s" % (time.time() - t0), flush=True)

    def run(eng, comps, want, with_drops=False):
        if with_drops:
            eng.debug_drops = []
        prods = eng.step(comps, cond, round_no=1)
        smis = {canon(getattr(p, "smiles", "") or "") for p in prods}
        drops = []
        if with_drops:
            drops = [d for d in (eng.debug_drops or []) if d.get("smiles") == want]
        return (want in smis), drops

    counts = {"过滤(classify/门控)": 0, "产物上限截断": 0, "模板没装载": 0,
              "真缺口": 0, "异常": 0}
    examples = []
    t1 = time.time()
    for i, row in sample.iterrows():
        comps = []
        for j, s in enumerate((row["r1"], row["r2"])):
            if s and Chem.MolFromSmiles(s):
                comps.append(Compound(smiles=s, name="R%d" % j, herb="(bench)"))
        want = canon(row["want"])
        if not comps or not want:
            counts["异常"] += 1
            continue
        try:
            hit_p, drops = run(prod, comps, want, with_drops=True)
            if hit_p:
                counts["异常"] += 1          # 抽样来自缺失集，理论上不该命中
                continue
            reasons = sorted({d.get("reason") for d in drops})
            if any(r in ("classify", "gate", "extent") for r in reasons):
                counts["过滤(classify/门控)"] += 1
                if len(examples) < 8:
                    examples.append((row["rid"], "过滤", ",".join(reasons)))
                continue
            # 同一套模板，只把每对产物上限提到 256
            prod.max_products_per_pair = 256
            hit_cap, _ = run(prod, comps, want)
            prod.max_products_per_pair = 32
            if hit_cap:
                counts["产物上限截断"] += 1
                if len(examples) < 8:
                    examples.append((row["rid"], "上限截断", ""))
                continue
            hit_r, _ = run(relax, comps, want)
            if hit_r:
                counts["模板没装载"] += 1
                if len(examples) < 8:
                    examples.append((row["rid"], "模板没装载", ""))
            else:
                counts["真缺口"] += 1
                if len(examples) < 8:
                    examples.append((row["rid"], "真缺口", ""))
        except Exception as ex:                        # noqa: BLE001
            counts["异常"] += 1
            print("  rid=%s 异常：%s: %s" % (row["rid"], type(ex).__name__, ex))
        if (i + 1) % 10 == 0:
            print("  ...%d/%d  %.0f s" % (i + 1, len(sample), time.time() - t1),
                  flush=True)

    n = sum(counts.values())
    print("\n归因（%d 条，%.0f s）" % (n, time.time() - t1))
    for k, v in counts.items():
        print("  %-8s %3d  %.1f%%" % (k, v, 100.0 * v / max(1, n)))
    print("\n个例：")
    for rid, why, note in examples:
        print("  rid=%-6s %-8s %s" % (rid, why, note))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
