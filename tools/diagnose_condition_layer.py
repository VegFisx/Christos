# -*- coding: utf-8 -*-
r"""条件层诊断：把 activation 从常数变成"真的随条件变"了吗？

## 为什么做这个
上一轮 `diagnose_false_positive.py` 的结论很硬：
54 个假阳性**全部**由 37 类里的 `B-H` 生成，**自抽模板一条没参与**。
也就是说：不是"噪声模板乱说话"，而是**条件层对同一反应类给出了同一个结论**。

本脚本把每条 HTE 记录的**真实条件**（催化剂/碱/溶剂/温度）构造出来，测三件事：
  ① **activation 分布**：在不同真实条件下，`B-H` 的 activation 是不是常数？
     - 若跨条件方差 ≈ 0 -> 条件层对该类**零判别力**（那 90% 假阳性就是它的直接后果）
  ② **within-pair 方差**：同一组底物（同一对 aryl/amine）的不同条件下，
     activation 会不会变？不变 = 换溶剂/碱/催化剂在引擎眼里没区别。
  ③ **成对判别力（AUC）**：同组内产率高的记录，activation 是否高于产率低的？
     AUC=0.5 就是瞎猜。

## 口径（先定死）
* 数据：`BH_HTE_Curated_Dataset_v20260219.csv`（27,497 行，逐行条件齐全）
* 条件构造：**用字段直接写进 `Conditions`**（不做字符串→类别的猜测）：
    solvent = Solvent Name；temperature = 记录里的温度（CSV 无该列 -> 用组内中位数/默认值）
    catalyst = Catalyst Name 映射到引擎认识的关键词（metal / acid / base / enzyme / None）
    reagents = 催化剂+碱的名字元组（引擎的 activation 只看温度/溶剂窗口与必需试剂）
* 引擎调用：`SmartReactEngine.cond_activation("B-H", cond)` —— 直接取条件层给的权重，
  **不跑枚举**（枚举与条件层无关，跑它只是浪费时间）
* 抽样：为了让"同组内多条件"存在，只取**组内记录数 ≥ --min-cond** 的组

用法:
    & $py -u tools\diagnose_condition_layer.py --limit 400
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
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
OUT = STAGE / "reports" / "condition_layer_diagnosis.json"

CATALYST_KW = {
    "metal": ("pd", "pt", "ni", "cu", "ru", "rh", "ir", "fe", "co", "catalyst",
              "binap", "xphos", "sphos", "brettphos", "ruphos", "jackiephos",
              "ad", "g3", "g4", "xantphos", "dppf", "tbu", "bippy"),
}
BASE_KW = ("cs2co3", "k2co3", "k3po4", "kotbu", "naotbu", "dbu", "mtbd", "et3n",
           "dipea", "naoh", "lioh", "tmg", "btmg", "carbonate", "phosphate",
           "base", "nah", "lda", "btpp")


def map_catalyst(name: str) -> str:
    t = str(name or "").strip().lower()
    if not t or t in ("none", "nan"):
        return "none"
    if any(k in t for k in CATALYST_KW["metal"]):
        return "metal"
    if any(k in t for k in BASE_KW):
        return "base"
    if "acid" in t or "hcl" in t or "tfa" in t:
        return "acid"
    return "other"


def auc(pairs):
    """pairs = [(score_hi_group, score_lo_group), ...]；返回 wins/ties/losses 与 AUC。"""
    wins = ties = losses = 0
    for a, b in pairs:
        if a > b:
            wins += 1
        elif a < b:
            losses += 1
        else:
            ties += 1
    n = wins + ties + losses
    return (wins + 0.5 * ties) / n if n else None, wins, ties, losses


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-cond", type=int, default=8, help="只取组内记录数 >= 此值的组")
    ap.add_argument("--limit", type=int, default=400, help="最多用多少组")
    ap.add_argument("--temp", type=float, default=100.0, help="CSV 无温度列的默认温度")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    t0 = time.time()
    groups = defaultdict(list)
    with open(CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("Aryl SMILES", "")).strip(),
                   str(row.get("Amine SMILES", "")).strip())
            if not key[0] or not key[1]:
                continue
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            groups[key].append({
                "y": y,
                "solvent": str(row.get("Solvent Name", "")).strip(),
                "catalyst": str(row.get("Catalyst Name", "")).strip(),
                "base": str(row.get("Base Name", "")).strip(),
                "source": str(row.get("Source", "")).strip(),
            })
    use = {k: v for k, v in groups.items() if len(v) >= a.min_cond}
    keys_sorted = sorted(use)[:a.limit]
    n_rows = sum(len(use[k]) for k in keys_sorted)
    print(f"CSV 组数 {len(groups):,}；组内记录数 >= {a.min_cond} 的组 {len(use):,}；"
          f"本次用 {len(keys_sorted)} 组 / {n_rows:,} 行")

    from model import Conditions
    from smartreact_engine import SmartReactEngine
    eng = SmartReactEngine()
    RULE = "B-H"

    scored = []
    for key in keys_sorted:
        for rec in use[key]:
            cond = Conditions(
                solvent=rec["solvent"].lower() or "unknown",
                temperature=a.temp, time_min=60.0, pH=7.0,
                catalyst=map_catalyst(rec["catalyst"]),
                atmosphere="air",
                reagents=tuple(x for x in (rec["catalyst"], rec["base"]) if x),
            )
            act, why = eng.cond_activation(RULE, cond)
            scored.append(dict(rec, key=key, activation=float(act), why=str(why)[:60]))

    acts = [s["activation"] for s in scored]
    uniq = Counter(round(x, 4) for x in acts)
    print(f"\n① activation 总分布：{dict(uniq.most_common(8))}")
    print(f"   唯一取值 {len(uniq)} 个；均值 {statistics.mean(acts):.3f}；"
          f"标准差 {statistics.pstdev(acts):.4f}")

    # ② 组内方差
    within = []
    for key in keys_sorted:
        v = [s["activation"] for s in scored if s["key"] == key]
        if len(v) >= 2:
            within.append(statistics.pstdev(v))
    n_zero_within = sum(1 for x in within if x == 0.0)
    print(f"\n② 组内（同底物对、换条件）activation 变化：")
    print(f"   有 {n_zero_within}/{len(within)} 个组的组内标准差 = 0（= 换条件在引擎眼里没区别）")
    if within:
        print(f"   组内标准差：均值 {statistics.mean(within):.4f}，最大 {max(within):.4f}")

    # ③ 成对 AUC：同组内 高产率 vs 低产率
    pairs = []
    for key in keys_sorted:
        v = [s for s in scored if s["key"] == key]
        hi = [s["activation"] for s in v if s["y"] >= 0.5]
        lo = [s["activation"] for s in v if s["y"] == 0.0]
        for h in hi:
            for l in lo:
                pairs.append((h, l))
    res = auc(pairs)
    print(f"\n③ 成对判别力（同组内 高产率 >=0.5 vs 零产率）：")
    if res[0] is None:
        print("   样本不足")
    else:
        print(f"   AUC = {res[0]:.4f}   wins {res[1]:,} / ties {res[2]:,} / losses {res[3]:,}"
              f"   （0.5 = 瞎猜）")

    # ④ 交叉表：按溶剂 / 催化剂看 activation
    cross_solv = defaultdict(list)
    cross_cat = defaultdict(list)
    for s in scored:
        cross_solv[s["solvent"] or "(空)"].append(s["activation"])
        cross_cat[map_catalyst(s["catalyst"])].append(s["activation"])
    print(f"\n④ 按溶剂的 activation 均值：")
    for k, v in sorted(cross_solv.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"   {k:<24} n={len(v):>5}  均值 {statistics.mean(v):.3f}")
    print(f"   按催化剂类别：")
    for k, v in sorted(cross_cat.items(), key=lambda kv: -len(kv[1])):
        print(f"   {k:<10} n={len(v):>5}  均值 {statistics.mean(v):.3f}")

    payload = {
        "what": "条件层诊断：activation 是否真的随真实条件变化、是否有判别力",
        "rule": RULE,
        "data": {"csv": CSV.name, "n_groups": len(groups),
                 "n_groups_used": len(keys_sorted), "n_rows_used": n_rows,
                 "min_cond": a.min_cond, "assumed_temperature_C": a.temp},
        "activation_distribution": {str(k): v for k, v in uniq.most_common(20)},
        "activation_mean": round(statistics.mean(acts), 4),
        "activation_stdev": round(statistics.pstdev(acts), 4),
        "within_pair_zero_variance_groups": n_zero_within,
        "within_pair_groups": len(within),
        "auc_by_pair": (None if res[0] is None else
                        {"auc": round(res[0], 4), "wins": res[1], "ties": res[2],
                         "losses": res[3]}),
        "activation_by_solvent": {k: {"n": len(v), "mean": round(statistics.mean(v), 4)}
                                  for k, v in cross_solv.items()},
        "activation_by_catalyst_class": {k: {"n": len(v), "mean": round(statistics.mean(v), 4)}
                                         for k, v in cross_cat.items()},
        "seconds": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\n-> {a.out}\n总用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
