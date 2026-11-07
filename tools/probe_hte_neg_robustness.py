# -*- coding: utf-8 -*-
r"""第十四轮 / 任务②附：HTE 反例集的**稳健性检查**。

担心：某个底物对"全 0"可能只是因为只测了 1~2 个条件（弱反例）。
本探针回答：全 0 的底物对各测了多少条件、跨几个来源？
          在"测得充分"（>=5 个条件）的子集上，引擎的假阳性率还是 94.9% 吗？

用法: python probe_hte_neg_robustness.py [充分子集评估上限，默认 300]
"""
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402
from rdkit import RDLogger  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

import mapped_chem as mc  # noqa: E402

RDLogger.DisableLog("rdApp.*")
CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 300


def main():
    df = pd.read_csv(CSV, low_memory=False)
    df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
    g = df.groupby(["Aryl SMILES", "Amine SMILES"]).agg(
        n=("_y", "size"), mx=("_y", "max"), src=("Source", "nunique")).reset_index()
    all0 = g[g["mx"] == 0]
    print("=" * 96)
    print(f"全 0 底物对 {len(all0):,} 个：每个测了多少条件 / 跨几个来源")
    print("=" * 96)
    print("  条件数分布:", dict(Counter(all0["n"].clip(upper=10)).most_common()))
    print("  来源数分布:", dict(Counter(all0["src"]).most_common()))
    for thr in (1, 3, 5, 10):
        sub = all0[all0["n"] >= thr]
        print(f"  >= {thr:>2} 个条件的全 0 底物对: {len(sub):,}")
    well = all0[all0["n"] >= 5]
    print()
    print(f"稳健子集（>=5 条件）{len(well):,} 对；评估前 {min(CAP, len(well))} 对")
    enum = ReactionEnumerator()
    t0 = time.time()
    claim = active = 0
    n_eval = 0
    for aryl, amine in well[["Aryl SMILES", "Amine SMILES"]].head(CAP).itertuples(index=False, name=None):
        sub = df[(df["Aryl SMILES"] == aryl) & (df["Amine SMILES"] == amine)]
        want = mc.canon_plain(str(sub["Product SMILES"].iloc[0]))
        try:
            res = enum.enumerate_pair(str(aryl), str(amine))
        except Exception:
            continue
        n_eval += 1
        got = set()
        for x in res:
            for p in x.products:
                cp = mc.canon_plain(p)
                if cp:
                    got.add(cp)
        if got:
            active += 1
        if want and want in got:
            claim += 1
    print(f"  评估 {n_eval} 对：引擎声称能发生 {claim} = {claim/max(1,n_eval):.1%}"
          f"（活性 {active/max(1,n_eval):.1%}）  耗时 {time.time()-t0:.0f}s")
    print()
    print("口径：这是【不带条件】的模板库声称率；若稳健子集上仍是 ~95%，")
    print("      说明假阳性不是「弱反例」造成的，而是引擎本身没有条件意识。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
