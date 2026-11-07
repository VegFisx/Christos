# -*- coding: utf-8 -*-
r"""A 方案前的信号探针：同一底物对下，条件特征能不能区分"成功 / 零产率"？

## 为什么先做这个
在训练任何模型之前，先回答"**数据里有没有可学的信号**"。
如果单变量都在 AUC≈0.5，训模型也是白训。

## 口径（先定死）
* 目标：同组底物（同一对 aryl/amine）内，预测"这条记录有产物（Yield ≥ 0.5）"vs"零产率"
  —— 即"同一对底物，换哪套条件能成"
* 特征：solvent / catalyst / base / source / additive
* **留组交叉验证（leave-group-out）**：给某组打分时，用**其它所有组**统计该条件取值的成功率，
  本组不参与 —— 否则同组内的成功记录会泄漏进分数，AUC 会被高估（第一版就踩了这个）
* 成对 AUC：组内 正例 vs 零产率 两两比较

输出：`reports/condition_signal_probe.json`

用法: & $py -u tools\probe_condition_signal.py --limit 300
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CSV = (STAGE / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data"
       / "BH_HTE_Curated_Dataset_v20260219.csv")
OUT = STAGE / "reports" / "condition_signal_probe.json"
POS = 0.5


def load(limit_groups: int, min_cond: int):
    groups = defaultdict(list)
    with open(CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            k = (str(row.get("Aryl SMILES", "")).strip(),
                 str(row.get("Amine SMILES", "")).strip())
            if not k[0] or not k[1]:
                continue
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            groups[k].append({
                "y": y,
                "solvent": str(row.get("Solvent Name", "")).strip() or "(空)",
                "catalyst": str(row.get("Catalyst Name", "")).strip() or "(空)",
                "base": str(row.get("Base Name", "")).strip() or "(空)",
                "source": str(row.get("Source", "")).strip(),
                "additive": str(row.get("Additive_present", "")).strip(),
            })
    use = {k: v for k, v in groups.items() if len(v) >= min_cond}
    keys = sorted(use)[:limit_groups]
    return {k: use[k] for k in keys}, len(groups), len(use)


FEATS = ["solvent", "catalyst", "base", "source", "additive"]


def leave_group_out_auc(data, feat):
    """留组打分 + 组内成对 AUC。"""
    gkeys = sorted(data)
    rows = [data[k] for k in gkeys]
    val = [[r[feat] for r in rws] for rws in rows]
    w = t = l = 0
    for gi in range(len(gkeys)):
        cnt = defaultdict(lambda: [0, 0])          # 取值 -> [正例, 总数]（不含本组）
        for gj in range(len(gkeys)):
            if gj == gi:
                continue
            for v, r in zip(val[gj], rows[gj]):
                cnt[v][1] += 1
                if r["y"] >= POS:
                    cnt[v][0] += 1
        tot = sum(c[1] for c in cnt.values())
        prior = (sum(c[0] for c in cnt.values()) / tot) if tot else 0.5
        score = {v: (c[0] / c[1] if c[1] else prior) for v, c in cnt.items()}
        hi = [score.get(v, prior) for v, r in zip(val[gi], rows[gi]) if r["y"] >= POS]
        lo = [score.get(v, prior) for v, r in zip(val[gi], rows[gi]) if r["y"] == 0.0]
        for x in hi:
            for y2 in lo:
                if x > y2:
                    w += 1
                elif x < y2:
                    l += 1
                else:
                    t += 1
    n = w + t + l
    return (round((w + 0.5 * t) / n, 4) if n else None), w, t, l, n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-cond", type=int, default=8)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    t0 = time.time()
    data, n_all, n_use = load(a.limit, a.min_cond)
    n_rows = sum(len(v) for v in data.values())
    print(f"组 {len(data)}（全量 {n_all:,}；组内 >= {a.min_cond} 条的 {n_use:,}）/ 行 {n_rows:,}")
    print("留组交叉验证（给某组打分时不含该组）：")

    results = {}
    for feat in FEATS:
        auc, w, t, l, n = leave_group_out_auc(data, feat)
        results[feat] = {"auc": auc, "wins": w, "ties": t, "losses": l, "pairs": n}
        print(f"  {feat:<10} AUC {auc}   wins {w:,} / ties {t:,} / losses {l:,}"
              f"   成对 {n:,}")

    # 条件组合的三个特征一起看（仍是留组，用"二元组取值"当分数）
    data2 = {k: [dict(r, solv_cat=f"{r['solvent']}|{r['catalyst']}|{r['base']}")
                 for r in v] for k, v in data.items()}
    auc, w, t, l, n = leave_group_out_auc(data2, "solv_cat")
    results["solvent+catalyst+base"] = {"auc": auc, "wins": w, "ties": t,
                                        "losses": l, "pairs": n}
    print(f"  {'溶+催+碱':<10} AUC {auc}   wins {w:,} / ties {t:,} / losses {l:,}")

    # 同一套条件在同一组里"有成有败"的比例
    per_cond = defaultdict(list)
    for v in data.values():
        for r in v:
            per_cond[(r["solvent"], r["catalyst"], r["base"])].append(r["y"])
    mixed = sum(1 for v in per_cond.values()
                if any(x >= POS for x in v) and any(x == 0 for x in v))
    print(f"\n  同一套条件在同一组内『既有成功又有零产率』的组合："
          f"{mixed:,} / {len(per_cond):,} = {mixed/max(1,len(per_cond)):.1%}")

    payload = {
        "what": "条件信号探针（留组交叉）：同一底物对下条件能否区分成功/零产率",
        "data": {"csv": CSV.name, "n_groups_all": n_all, "n_groups_used": len(data),
                 "n_rows": n_rows, "min_cond": a.min_cond, "pos_threshold": POS},
        "auc_leave_group_out": results,
        "condition_combo_mixed_outcome": {
            "n_combos": len(per_cond), "n_mixed": mixed,
            "share": round(mixed / max(1, len(per_cond)), 4)},
        "seconds": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\n-> {a.out}\n用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
