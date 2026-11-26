# -*- coding: utf-8 -*-
"""覆盖缺口诊断：没有目标产物的反应，集中在哪些类别 / 底物类型 / 模板族。

输入：按生产配置构建的候选表（默认 candidates_cli.parquet）。
输出：控制台摘要（不写文件）。

用法：
  python tools\\diagnose_coverage_gaps.py
  python tools\\diagnose_coverage_gaps.py --table reports\\candidate_table\\candidates_cli.parquet --meta reports\\candidate_table\\meta_cli.json
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import candidate_table as CT  # noqa: E402

COL = ["rid", "want", "rule", "tpl", "n_cand", "n_pos", "src_ha", "s_rings",
       "s_arom", "s_hba", "s_hbd", "rxn_class", "r1", "r2"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default=str(CT.DEFAULT_DIR / "candidates_cli.parquet"))
    ap.add_argument("--meta", default=str(CT.DEFAULT_DIR / "meta_cli.json"))
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()

    df, meta = CT.load(parquet=a.table, meta=CT.load_meta(a.meta), columns=COL)
    g = df.groupby("rid", sort=False)
    rxn = g.first().reset_index()
    rxn["n_cand"] = g.size().values
    rxn["miss"] = (rxn["n_pos"] == 0).astype(int)
    n = len(rxn)
    print("反应 %d / 命中 %d / 缺失 %d（%.2f%%）"
          % (n, int((rxn["miss"] == 0).sum()), int(rxn["miss"].sum()),
             100.0 * rxn["miss"].mean()))

    print("\n候选数：命中中位 %d / 缺失中位 %d"
          % (int(rxn.loc[rxn.miss == 0, "n_cand"].median()),
             int(rxn.loc[rxn.miss == 1, "n_cand"].median())))

    print("\n按反应类别（前 %d 类）" % a.top)
    tab = rxn.groupby("rxn_class").agg(n=("rid", "size"), miss=("miss", "sum"))
    tab["rate"] = (tab["miss"] / tab["n"]).round(3)
    tab = tab.sort_values("n", ascending=False).head(a.top)
    for cls, row in tab.iterrows():
        print("  class %-4s n=%-5d 缺失 %-4d %.1f%%"
              % (cls, row["n"], row["miss"], 100 * row["rate"]))

    print("\n按底物重原子数分桶")
    bins = [0, 15, 20, 25, 30, 40, 60, 10 ** 9]
    lab = ["≤15", "16-20", "21-25", "26-30", "31-40", "41-60", ">60"]
    b = pd.cut(rxn["src_ha"], bins=bins, labels=lab, right=True)
    tab = rxn.groupby(b, observed=True).agg(n=("rid", "size"), miss=("miss", "sum"))
    for k, row in tab.iterrows():
        print("  %-6s n=%-5d 缺失 %-4d %.1f%%"
              % (k, row["n"], row["miss"], 100.0 * row["miss"] / max(1, row["n"])))

    print("\n按候选数分桶")
    bins2 = [0, 10, 20, 35, 60, 10 ** 9]
    lab2 = ["≤10", "11-20", "21-35", "36-60", ">60"]
    b2 = pd.cut(rxn["n_cand"], bins=bins2, labels=lab2, right=True)
    tab = rxn.groupby(b2, observed=True).agg(n=("rid", "size"), miss=("miss", "sum"))
    for k, row in tab.iterrows():
        print("  %-6s n=%-5d 缺失 %-4d %.1f%%"
              % (k, row["n"], row["miss"], 100.0 * row["miss"] / max(1, row["n"])))

    # 哪类规则出现在缺失反应里（反应级覆盖率）
    print("\n规则出现率（缺失 vs 命中）")
    miss_rids = set(rxn.loc[rxn.miss == 1, "rid"].tolist())
    hit_rids = set(rxn.loc[rxn.miss == 0, "rid"].tolist())
    by_rule_miss = {r: set() for r in df["rule"].unique()}
    by_rule_hit = {r: set() for r in df["rule"].unique()}
    for rid, rule in zip(df["rid"].values, df["rule"].values):
        (by_rule_miss if rid in miss_rids else by_rule_hit)[rule].add(rid)
    rows = []
    for r in by_rule_miss:
        nm, nh = len(by_rule_miss[r]), len(by_rule_hit[r])
        if nm + nh < 50:
            continue
        rows.append((r, nm / max(1, len(miss_rids)), nh / max(1, len(hit_rids)), nm + nh))
    rows.sort(key=lambda x: -x[3])
    for r, pm, ph, tot in rows[:a.top]:
        print("  %-32s 缺失反应中 %5.1f%% / 命中反应中 %5.1f%%（%d）"
              % (r, 100 * pm, 100 * ph, tot))

    # 产物元素类型
    print("\n缺失反应的产物是否含特殊元素")
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    groups = {"S": 0, "P": 0, "卤素": 0, "金属": 0}
    tot = 0
    for smi in rxn.loc[rxn.miss == 1, "want"].tolist():
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            continue
        tot += 1
        els = {a.GetSymbol() for a in m.GetAtoms()}
        if "S" in els:
            groups["S"] += 1
        if "P" in els:
            groups["P"] += 1
        if els & {"F", "Cl", "Br", "I"}:
            groups["卤素"] += 1
        if els & {"Fe", "Cu", "Pd", "Ni", "Zn", "Mg", "Li", "Na", "K", "B", "Si"}:
            groups["金属"] += 1
    for k, v in groups.items():
        print("  %-4s %d / %d（%.1f%%）" % (k, v, tot, 100.0 * v / max(1, tot)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
