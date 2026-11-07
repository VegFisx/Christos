# -*- coding: utf-8 -*-
r"""第十四轮 / 任务②：ORD 之外的反例数据 —— HTE（Buchwald-Hartwig）真实失败条件 + 首次实测。

数据来源（已下载，Apache-2.0，1.84 MB）：
  Zenodo 19635488  schwallergroup/bh-hte-ood
  data/BH_HTE_Curated_Dataset_v20260219.csv
  27,497 条 HTE 反应 / 8 个来源（JNJ HTE 2024、Dreher Doyle 2018、Merck 2025、Roche 2023、
  HiTEA 2024、Dreher 2014、AZ ELN 2023、Dreher 2016），含 Yield 与 manuscript 的二分 labels。

为什么它比 ORD 强（实测）：ORD 243 万条全是正例；这张表 **38.9% 的行 Yield == 0**，
且同一底物对在不同条件下既有 0 也有 >0 —— 这是【条件级反例】，ORD 完全没有。

三口径（写死）：
  NEG_SUB  底物级反例：同一 (Aryl, Amine) 的所有行 Yield 全为 0
  NEG_COND 条件级反例：某一行 Yield == 0
  POS_CTRL 正对照：有对比的底物对里 Yield > 0 的行

引擎侧两个测量：
  A. 模板库（**不带条件**）声称能发生的比例：负例 vs 正对照
       → 假阳性率 = 引擎在 NEG_SUB 上产出【目标产物】的比例
       → 必须同时报"引擎活性"（产出任何产物），否则 0% 可能只是没规则可用
  B. 条件门控的判别力：在有对比的底物对（同底物、不同条件）上，
     对每个条件算 cond_activation(反应类, 条件)，看**成功条件的分数是否高于失败条件**
       → 指标 = AUC（Mann-Whitney；0.5 = 毫无判别力）
     条件映射（HTE 表没有温度列，这是已知局限）：
       温度 -> 用该类 ORD 中位数（B-H: 100 °C）
       溶剂 -> row['Solvent Name'] 走我们的溶剂词表
       试剂 -> row['Base SMILES']（碱）

用法: python hte_negatives.py [每类最多评估多少对，默认 1500]
输出: reports/hte_negatives_summary.json + reports/hte_negatives.jsonl
"""
import json
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
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core",
           STAGE / "conditions", STAGE / "rules"):
    sys.path.insert(0, str(_p))

import pandas as pd  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

import mapped_chem as mc  # noqa: E402
from model import Conditions, solvent_class  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
OUT_JSONL = STAGE / "reports" / "hte_negatives.jsonl"
OUT_SUM = STAGE / "reports" / "hte_negatives_summary.json"
CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
RXN_CLASS = "B-H"          # 实测：templates.txt 里 B-H = Buchwald-Hartwig（X-Bromide + Amine）


def main():
    t0 = time.time()
    if not CSV.exists():
        print(f"!! 数据不在: {CSV}")
        return 1
    df = pd.read_csv(CSV, low_memory=False)
    df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
    print("=" * 96)
    print(f"HTE 表：{len(df):,} 行")
    print("=" * 96)
    print(f"  Yield == 0 : {int((df['_y'] == 0).sum()):,} ({(df['_y'] == 0).mean():.1%})"
          f"   Yield > 0 : {int((df['_y'] > 0).sum()):,}")
    if "labels" in df.columns:
        lab = pd.to_numeric(df["labels"], errors="coerce")
        print(f"  manuscript labels 列：二值分布 {dict(lab.value_counts().head(4))}"
              f"  | 与 Yield==0 的一致率 "
              f"{( (lab == 0) == (df['_y'] == 0) ).mean():.1%}")
    for k, v in df["Source"].value_counts().items():
        z = int((df.loc[df["Source"] == k, "_y"] == 0).sum())
        print(f"    {k:<22} {v:>6} 行，0 收率 {z:>6} ({z/v:.0%})")

    g = df.groupby(["Aryl SMILES", "Amine SMILES"])["_y"]
    agg = g.agg(["count", "max", "min"]).reset_index()
    pair_all0 = agg[agg["max"] == 0]
    pair_contrast = agg[(agg["min"] == 0) & (agg["max"] > 0)]
    print()
    print(f"  底物对 {len(agg):,}：全 0 {len(pair_all0):,} | 有对比 {len(pair_contrast):,}"
          f" | 全 >0 {int((agg['min'] > 0).sum()):,}")

    # ---------------- 反例集落盘 ----------------
    n_neg = 0
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for _, r in df.iterrows():
            if r["_y"] != 0:
                continue
            f.write(json.dumps({
                "source": r.get("Source"),
                "aryl": r.get("Aryl SMILES"), "amine": r.get("Amine SMILES"),
                "product": r.get("Product SMILES"),
                "catalyst": r.get("Catalyst Name"), "catalyst_smiles": r.get("Catalyst SMILES"),
                "base": r.get("Base Name"), "base_smiles": r.get("Base SMILES"),
                "solvent": r.get("Solvent Name"), "solvent_smiles": r.get("Solvent SMILES"),
                "yield": 0.0, "label": "NEG_COND",
            }, ensure_ascii=False) + "\n")
            n_neg += 1
    print(f"  条件级反例写入 {n_neg:,} 条 -> {OUT_JSONL.name}")

    # ---------------- A. 模板库（无条件）声称率 ----------------
    enum = ReactionEnumerator()

    def eval_pair(aryl, amine, product):
        try:
            res = enum.enumerate_pair(str(aryl), str(amine))
        except Exception:
            return False, False, []
        want = mc.canon_plain(str(product)) if product else None
        got, target_names, any_names = set(), set(), set()
        for x in res:
            for p in x.products:
                cp = mc.canon_plain(p)
                if cp:
                    got.add(cp)
                    any_names.add(x.reaction_name)
                    if want and cp == want:
                        target_names.add(x.reaction_name)
        return (bool(want) and want in got), bool(got), sorted(target_names), sorted(any_names)

    neg_pairs = pair_all0.head(CAP)
    pos_rows = df[df["_y"] > 0].merge(
        pair_contrast[["Aryl SMILES", "Amine SMILES"]],
        on=["Aryl SMILES", "Amine SMILES"], how="inner").head(CAP)
    print()
    print(f"测量 A：底物级反例 {len(neg_pairs):,} 对；正对照 {len(pos_rows):,} 条", flush=True)

    stat = Counter()
    target_class = Counter()
    any_class = Counter()
    t1 = time.time()
    neg_claim = neg_active = 0
    for i, r in enumerate(neg_pairs.itertuples(index=False, name=None), 1):
        aryl, amine = r[0], r[1]
        sub = df[(df["Aryl SMILES"] == aryl) & (df["Amine SMILES"] == amine)]
        prod = sub["Product SMILES"].iloc[0]
        hit, active, tnames, anames = eval_pair(aryl, amine, prod)
        stat["NEG_评估"] += 1
        neg_claim += 1 if hit else 0
        neg_active += 1 if active else 0
        for n in tnames:
            target_class[n] += 1
        for n in anames:
            any_class[n] += 1
        if i % 300 == 0:
            print(f"    反例 {i}/{len(neg_pairs)}  {time.time()-t1:.0f}s", flush=True)

    pos_hit = pos_active = 0
    for i, r in enumerate(pos_rows[["Aryl SMILES", "Amine SMILES", "Product SMILES"]]
                          .itertuples(index=False, name=None), 1):
        aryl, amine, prod = r
        hit, active, tnames, anames = eval_pair(aryl, amine, prod)
        stat["POS_评估"] += 1
        pos_hit += 1 if hit else 0
        pos_active += 1 if active else 0
        for n in tnames:
            target_class[n] += 1
        for n in anames:
            any_class[n] += 1
        if i % 300 == 0:
            print(f"    正对照 {i}/{len(pos_rows)}  {time.time()-t1:.0f}s", flush=True)

    ne, pe = max(1, stat["NEG_评估"]), max(1, stat["POS_评估"])
    print()
    print(f"  A. 模板库（无条件）：负例上声称能发生 {neg_claim}/{ne} = {neg_claim/ne:.1%}"
          f"（活性 {neg_active/ne:.1%}）")
    print(f"                        正对照上复现目标产物 {pos_hit}/{pe} = {pos_hit/pe:.1%}"
          f"（活性 {pos_active/pe:.1%}）")

    # ---------------- B. 条件门控的判别力（同底物、不同条件） ----------------
    eng = SmartReactEngine(gate_conditions=True)
    ctab = eng.cond_table.get(RXN_CLASS) or {}
    tdef = float(((ctab.get("temp_C") or {}).get("default")) or 100.0)
    rows = df[df["_y"].notna()].copy()
    contrast_keys = set(zip(pair_contrast["Aryl SMILES"], pair_contrast["Amine SMILES"]))
    rows = rows[[k in contrast_keys for k in zip(rows["Aryl SMILES"], rows["Amine SMILES"])]]

    def score_of(row):
        sol = str(row.get("Solvent Name") or "").strip()
        cond = Conditions(solvent=sol if sol else "organic",
                          temperature=tdef,
                          catalyst="metal",
                          reagents=(str(row.get("Base SMILES") or ""),) if row.get("Base SMILES") else ())
        s, why = eng.cond_activation(RXN_CLASS, cond)
        return s, why, solvent_class(sol)

    wins = ties = losses = 0
    pair_mixed = 0
    detail = []
    for (aryl, amine), sub in rows.groupby(["Aryl SMILES", "Amine SMILES"]):
        succ = [r for _, r in sub.iterrows() if r["_y"] > 0]
        fail = [r for _, r in sub.iterrows() if r["_y"] == 0]
        if not succ or not fail:
            continue
        pair_mixed += 1
        s_succ = [score_of(r)[0] for r in succ]
        s_fail = [score_of(r)[0] for r in fail]
        for a in s_succ:
            for b in s_fail:
                if a > b:
                    wins += 1
                elif a == b:
                    ties += 1
                else:
                    losses += 1
        if len(detail) < 5:
            detail.append({"pair": [str(aryl)[:40], str(amine)[:40]],
                           "succ_scores": sorted(set(s_succ)),
                           "fail_scores": sorted(set(s_fail)),
                           "succ_solvents": sorted({score_of(r)[2] for r in succ}),
                           "fail_solvents": sorted({score_of(r)[2] for r in fail})})
    auc = (wins + 0.5 * ties) / max(1, (wins + ties + losses))
    print()
    print(f"  B. 条件门控判别力（{pair_mixed} 个有对比的底物对，"
          f"{wins+ties+losses:,} 对(成功,失败)比较）")
    print(f"     成功条件分数 > 失败条件：{wins:,}  < ：{losses:,}  相等：{ties:,}")
    print(f"     AUC = {auc:.3f}   （0.5 = 毫无判别力）")
    for d in detail:
        print(f"     e.g. 成功条件分 {d['succ_scores']} (溶剂 {d['succ_solvents']}) "
              f"vs 失败 {d['fail_scores']} (溶剂 {d['fail_solvents']})")

    summary = {
        "scratch": "HTE (Buchwald-Hartwig) 反例集 + 引擎首次实测",
        "data": {"csv": CSV.name, "rows": int(len(df)),
                 "yield_zero_rows": int((df["_y"] == 0).sum()),
                 "yield_zero_rate": float((df["_y"] == 0).mean()),
                 "pairs": int(len(agg)), "pairs_all_zero": int(len(pair_all0)),
                 "pairs_contrast": int(len(pair_contrast)),
                 "sources": {k: int(v) for k, v in df["Source"].value_counts().items()}},
        "negatives_jsonl_rows": n_neg,
        "A_template_library_unconditional": {
            "neg_pairs_evaluated": stat["NEG_评估"],
            "neg_claims_target_product": neg_claim,
            "neg_false_positive_rate": neg_claim / ne,
            "neg_engine_active": neg_active,
            "pos_evaluated": stat["POS_评估"],
            "pos_reproduced_target": pos_hit,
            "pos_recall": pos_hit / pe,
            "pos_engine_active": pos_active,
            "target_class_hits": dict(target_class.most_common(10)),
            "any_class_hits": dict(any_class.most_common(10)),
        },
        "B_condition_gate": {
            "reaction_class_used": RXN_CLASS,
            "assumed_temperature_C": tdef,
            "pairs_with_contrast": pair_mixed,
            "comparisons": wins + ties + losses,
            "wins": wins, "ties": ties, "losses": losses,
            "auc": auc,
            "examples": detail,
        },
        "seconds": round(time.time() - t0, 1),
    }
    OUT_SUM.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n结果 -> {OUT_SUM.name} / {OUT_JSONL.name}   总耗时 {time.time()-t0:.0f}s")
    enum.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
