# -*- coding: utf-8 -*-
r"""第 1 件：把"我们到底对不对"变成数字（用现成的带标注 HTE 数据当判卷答案）。

## 判卷答案从哪来
`data/external/bh-hte-ood/.../BH_HTE_Curated_Dataset_v20260219.csv`
（27,497 行 Buchwald-Hartwig 高通量实验：Aryl SMILES / Amine SMILES /
 Product SMILES / Yield / Solvent Name / Source）

## 口径（先定死，跑之前写清楚）
* **组** = 一组 (芳基卤, 胺) 的全部条件记录聚合：
  - `y_max >= --pos`（默认 0.5）-> **正例**（这组底物确实成反应）
  - `y_max == 0`               -> **负例**（所有条件都试过，全零）
  - 中间值                      -> **灰例**（不进指标）
* **一批一跑**：正例全放一次引擎调用、负例全放另一次（避免逐对调用太慢）。
  ⚠ 这带来的已知混淆：同批内不同组的底物会互相配对，理论上可能"碰巧"产出别组的目标 ——
    所以负例假阳性是**上界**（真值只会更低）。
* **目标产物判定**：CSV 的 Product SMILES 经 RDKit canonical 后，是否出现在引擎输出里。
* **指标**：正例召回、负例假阳性（上界）、按数据来源分层。

## 重要限制（不写清楚会被误读）
1. 本数据**全是 Buchwald-Hartwig 耦合（单一方向）**，没有"正逆两方向都出现"的样本
   —— 所以**它测不了方向层**，只能测"引擎会不会在不该反应的地方乱产生产物"。
2. 条件被固定为煎煮（CSV 没有统一温度列）-> 所有组的 activation 相同，**无判别力**，
   所以本脚本**不报 AUC**（报了也是假的）。
3. 想直接验证"水相里酯化该不该发生"，需要含正逆两方向的数据 —— 本数据没有。

用法:
    & $py -u tools\measure_hte_validation.py --limit 240
"""
from __future__ import annotations

import argparse
import csv
import json
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
OUT = STAGE / "reports" / "hte_validation_result.json"


def canon(s):
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(str(s or ""))
    return Chem.MolToSmiles(m) if m else None


def load_groups(pos_thr: float):
    groups = defaultdict(list)
    n_bad_row = 0
    with open(CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("Aryl SMILES", "")).strip(),
                   str(row.get("Amine SMILES", "")).strip())
            if not key[0] or not key[1]:
                n_bad_row += 1
                continue
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            groups[key].append({
                "y": y,
                "solvent": str(row.get("Solvent Name", "")).strip(),
                "product": str(row.get("Product SMILES", "")).strip(),
                "source": str(row.get("Source", "")).strip(),
            })
    pos, neg, grey = [], [], []
    for (aryl, amine), rows in groups.items():
        ymax = max(r["y"] for r in rows)
        rec = {"aryl": aryl, "amine": amine, "y_max": round(ymax, 4),
               "n_cond": len(rows),
               "product": Counter(r["product"] for r in rows).most_common(1)[0][0],
               "solvent": Counter(r["solvent"] for r in rows).most_common(1)[0][0],
               "source": rows[0]["source"]}
        (neg if ymax == 0.0 else (pos if ymax >= pos_thr else grey)).append(rec)
    return pos, neg, grey, len(groups), n_bad_row


def pick(lst, n):
    lst = sorted(lst, key=lambda r: (r["aryl"], r["amine"]))
    if n >= len(lst) or n <= 0:
        return lst
    step = len(lst) / n
    return [lst[int(i * step)] for i in range(n)]


def rate(rows, key):
    return (sum(1 for r in rows if r[key]) / len(rows)) if rows else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=240, help="每类取多少组（正/负各一半）")
    ap.add_argument("--pos", type=float, default=0.5, help="正例阈值（组内 Yield 最大值）")
    ap.add_argument("--temp", type=float, default=100.0, help="CSV 无温度时的默认温度")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    t0 = time.time()
    posall, negall, grey, n_all, n_bad_row = load_groups(a.pos)
    pos, neg = pick(posall, a.limit // 2), pick(negall, a.limit // 2)
    print(f"CSV 聚合出 {n_all:,} 组底物（跳过无结构 {n_bad_row} 行）")
    print(f"  全量：正例(y_max>={a.pos}) {len(posall):,} / 负例(y_max==0) {len(negall):,} / "
          f"灰例 {len(grey):,}")
    print(f"  抽样进入测试：正 {len(pos)}、负 {len(neg)}")
    print(f"  负例全零率（组级）: {len(negall)/n_all:.1%}")

    from engine import Compound
    from smartreact_engine import SmartReactEngine
    import templates as T

    eng = SmartReactEngine()
    # HTE 是 23 类里没有的"条件表外"反应类型；温度用 CSV 的通用范围（此处给默认值）
    base = T.get_template("煎煮")
    cond = type(base)(solvent="dmso", temperature=a.temp, time_min=60.0, pH=7.0,
                      catalyst="metal", atmosphere="air",
                      reagents=("CS(=O)(=O)O[Pd]1",))
    print(f"条件：{cond.describe()}")
    print(f"        （★ 统一取 DMSO/{a.temp:.0f}°C/金属催化剂 —— CSV 无逐行统一温度列，"
          f"这一步是**假设**）")
    print(f"      {eng.extra_template_note}")
    print(f"      {eng.mono_template_note}")

    results = {}
    for label, rows in (("pos", pos), ("neg", neg)):
        t1 = time.time()
        # ★★ 必须【逐对】跑，不能把 200+200 个分子一起丢进去 ★★
        #   第一次这样跑（--limit 400）得到"正例召回 4%"，那是假象：
        #   200×200 = 40,000 对 > max_pairs(4000) -> 被截断，绝大多数组合根本没被枚举。
        #   同一个坑在项目里出现过（底物成分数变化导致能力数字漂移），这次又踩一次。
        out_rows = []
        n_active = 0
        rule_hits = Counter()
        for i, r in enumerate(rows):
            comps = [Compound(smiles=r["aryl"], name=f"A{i}", herb="HTE"),
                     Compound(smiles=r["amine"], name=f"B{i}", herb="HTE")]
            prods = eng.step(comps, cond, round_no=1)
            got = {p.smiles for p in prods}
            if got:
                n_active += 1
            for p in prods:
                rule_hits[p.rule_name] += 1
            tgt = canon(r["product"])
            out_rows.append(dict(r, target=tgt, reproduced=bool(tgt and tgt in got),
                                 n_products=len(got)))
        results[label] = out_rows
        print(f"  {label}: {len(rows)} 组 -> 逐对跑完，"
              f"{n_active} 组至少产出一个分子（{time.time()-t1:.1f}s）")
        print(f"        规则命中分布 {dict(rule_hits.most_common(4))}")

    rec_pos = rate(results["pos"], "reproduced")
    fp_neg = rate(results["neg"], "reproduced")
    sources = sorted({r["source"] for r in results["pos"] + results["neg"]})
    per_source = {}
    for s in sources:
        pr = [r for r in results["pos"] if r["source"] == s]
        nr = [r for r in results["neg"] if r["source"] == s]
        per_source[s] = {"n_pos": len(pr), "n_neg": len(nr),
                         "pos_recall": rate(pr, "reproduced"),
                         "neg_fp": rate(nr, "reproduced")}

    print()
    print("=" * 92)
    print("判卷结果")
    print("=" * 92)
    n_pr = sum(1 for r in results["pos"] if r["reproduced"])
    n_nf = sum(1 for r in results["neg"] if r["reproduced"])
    print(f"  正例召回（目标产物被复现）:  {rec_pos:>6.1%}   ({n_pr}/{len(results['pos'])})")
    print(f"  负例假阳性（上界，见口径）:  {fp_neg:>6.1%}   ({n_nf}/{len(results['neg'])})")
    print(f"  全量数据上的组级全零率:      {len(negall)/n_all:>6.1%}")
    print("\n  按数据来源分层：")
    for s, d in per_source.items():
        pr = f"{d['pos_recall']:.0%}" if d["pos_recall"] is not None else "-"
        fp = f"{d['neg_fp']:.0%}" if d["neg_fp"] is not None else "-"
        print(f"    {s:<20} 正 {d['n_pos']:>3} (召回 {pr:>4})   负 {d['n_neg']:>3} (假阳性 {fp:>4})")

    payload = {
        "what": "用 HTE 带标注数据检验现有引擎：正例=确实有产物 / 负例=所有条件全零",
        "caveat": [
            "① 本数据全是 Buchwald-Hartwig 耦合（单一方向）-> **测不了方向层**（没有正逆双向样本）",
            "② 条件被统一假设为 DMSO/100C/金属催化剂（CSV 无逐行统一温度列）-> activation 无差异，故不报 AUC",
            "③ 同批内互相配对的混淆 -> 负例假阳性是**上界**",
            "④ 负例定义=组内所有条件零产率，仍可能有痕量产物",
        ],
        "data": {"csv": CSV.name, "n_groups": n_all, "n_bad_rows": n_bad_row,
                 "n_pos_all": len(posall), "n_neg_all": len(negall), "n_grey": len(grey),
                 "pos_threshold": a.pos, "group_level_zero_rate": len(negall) / n_all},
        "engine": {"extra": eng.extra_template_note, "mono": eng.mono_template_note,
                   "cond": cond.describe()},
        "pos_recall": rec_pos, "neg_false_positive_upper_bound": fp_neg,
        "per_source": per_source,
        "rows": results,
        "seconds": round(time.time() - t0, 1),
    }
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"\n-> {a.out}")
    print(f"总用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
