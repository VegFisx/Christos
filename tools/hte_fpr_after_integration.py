# -*- coding: utf-8 -*-
r"""第十五轮 / 任务 A：把 ORD 自抽模板接进引擎后，**假阳性的代价**是多少？

背景（已实测）：
  · 现有引擎（9770 模板）在 HTE 实测全 0 的底物对上假阳性 94.9%；正对照召回 64.0%。
  · 上一轮从 ORD 抽到 5,670 条正向模板：支持≥5 的保守版能 +4.88 pp（test 覆盖率 30.0%→34.9%），
    支持≥1 的宽松版能 +9.59 pp，但宽松度 33.8%。
  → 本脚本回答：**接进去之后，HTE 上的假阳性变成多少？召回变成多少？**

口径（写死）：
  样本：HTE 表（Buchholz-Hartwig，Zenodo 19635488）
    NEG = 底物级反例（该底物对所有条件 Yield==0 的底物对）
    POS = 正对照（有对比的底物对里 Yield>0 的行）
  判定：把 (Aryl, Amine) 作为两个 Compound 喂 **引擎 step()**（不是裸枚举器 —— 这样
        max_products_per_pair、副产物过滤、条件门控都包含在内），看目标产物是否出现。
  三种配置：
    baseline        不加载额外模板（现有行为）
    +mined_K5       支持数>=5（91 条，保守）
    +mined_K1       支持数>=1（600 条上限，宽松）
  指标：NEG 假阳性率 / POS 召回 / 引擎活性（产出任何产物）

用法: python hte_fpr_after_integration.py [NEG 上限] [POS 上限]
输出: reports/hte_fpr_after_integration.json
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
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402
from engine import Compound  # noqa: E402
from model import Conditions  # noqa: E402
from smartreact_engine import SmartReactEngine  # noqa: E402

RDLogger.DisableLog("rdApp.*")

CSV = STAGE / "data" / "external" / "bh-hte-ood" / \
    "schwallergroup-bh-hte-ood-a277041" / "data" / "BH_HTE_Curated_Dataset_v20260219.csv"
TMPL = STAGE / "reports" / "mined_forward_templates.jsonl"
OUT = STAGE / "reports" / "hte_fpr_after_integration.json"

NEG_CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 1993
POS_CAP = int(sys.argv[2]) if len(sys.argv) > 2 else 2500


def run_config(name, extra_path, min_support, neg_pairs, pos_rows, t0, gate_extra=False):
    # ★ 第十七轮修正：第十六轮把 extra_templates_path=None 的含义改成了「走默认路径（默认开）」，
    #   于是本函数原来的 baseline 配置（传 None 期望"关闭"）会静默变成 K5 档。
    #   现在显式化：extra_path 为 None/False -> 显式 use_extra_templates=False。
    use_extra = extra_path is not None and extra_path is not False
    eng = SmartReactEngine(gate_conditions=True,
                           extra_templates_path=(extra_path if use_extra else None),
                           use_extra_templates=use_extra,
                           extra_template_min_support=min_support,
                           extra_requires_accepted_pair=gate_extra)
    print(f"\n[{name}] 额外模板：{eng.extra_template_note}"
          f"   非孤儿规则：{'开' if gate_extra else '关'}", flush=True)

    def claim(aryl, amine, product):
        comps = [Compound(smiles=str(aryl), name="aryl", herb="hte"),
                 Compound(smiles=str(amine), name="amine", herb="hte")]
        try:
            prods = eng.step(comps, None, round_no=1)
        except Exception:
            return False, False, 0, 0
        want = mc.canon_plain(str(product)) if product else None
        got = set()
        n_extra = 0
        for p in prods:
            if getattr(p, "rule_name", "") == "mined_extra":
                n_extra += 1
            cs = mc.canon_plain(p.smiles)
            if cs:
                got.add(cs)
        return (bool(want) and want in got), bool(got), len(got), n_extra

    # ★ 第十七轮：额外统计三个数 —— 自抽模板在负例上"创造"了多少活性对 / 多少产物
    neg_claim = neg_active = neg_prod = 0
    neg_extra_only = neg_extra_prod = 0
    for aryl, amine, prod in neg_pairs:
        hit, active, nprod, nextra = claim(aryl, amine, prod)
        neg_claim += 1 if hit else 0
        neg_active += 1 if active else 0
        neg_prod += nprod
        neg_extra_prod += nextra
        if active and nextra == nprod and nprod > 0:
            neg_extra_only += 1          # 这一对的产物【全部】来自自抽模板 -> 孤儿对
    pos_claim = pos_active = pos_prod = pos_extra_prod = 0
    for aryl, amine, prod in pos_rows:
        hit, active, nprod, nextra = claim(aryl, amine, prod)
        pos_claim += 1 if hit else 0
        pos_active += 1 if active else 0
        pos_prod += nprod
        pos_extra_prod += nextra
    ne, pe = max(1, len(neg_pairs)), max(1, len(pos_rows))
    res = {
        "config": name,
        "extra_templates": eng.extra_template_note,
        "n_extra_compiled": len(eng.extra_templates),
        "extra_requires_accepted_pair": bool(gate_extra),
        "neg_n": len(neg_pairs), "neg_claims": neg_claim,
        "neg_false_positive_rate": neg_claim / ne,
        "neg_engine_active": neg_active / ne,
        # ★ 不饱和的指标：假阳性率已经 94.9%（天花板 100%），
        #   所以还要看"负例上到底多吐了多少产物"——它没有天花板。
        "neg_products_total": neg_prod,
        "neg_products_per_pair": neg_prod / ne,
        "neg_extra_products": neg_extra_prod,
        "neg_extra_products_per_pair": neg_extra_prod / ne,
        "neg_extra_only_pairs": neg_extra_only,
        "neg_extra_only_rate": neg_extra_only / ne,
        "pos_n": len(pos_rows), "pos_claims": pos_claim,
        "pos_recall": pos_claim / pe,
        "pos_engine_active": pos_active / pe,
        "pos_products_total": pos_prod,
        "pos_products_per_row": pos_prod / pe,
        "pos_extra_products": pos_extra_prod,
        "seconds": round(time.time() - t0, 1),
    }
    print(f"  NEG 假阳性 {neg_claim}/{ne} = {res['neg_false_positive_rate']:.1%}"
          f"（活性 {res['neg_engine_active']:.1%}；负例上产物总数 {neg_prod:,}"
          f" = {res['neg_products_per_pair']:.2f}/对）")
    print(f"      其中自抽模板贡献 {neg_extra_prod:,} 条 ({res['neg_extra_products_per_pair']:.2f}/对)；"
          f"【孤儿对】(产物全来自自抽模板) {neg_extra_only}/{ne} = {res['neg_extra_only_rate']:.1%}")
    print(f"  POS 召回   {pos_claim}/{pe} = {res['pos_recall']:.1%}"
          f"（活性 {res['pos_engine_active']:.1%}；产物总数 {pos_prod:,}"
          f" = {res['pos_products_per_row']:.2f}/条）", flush=True)
    return res


def main():
    t0 = time.time()
    df = pd.read_csv(CSV, low_memory=False)
    df["_y"] = pd.to_numeric(df["Yield"], errors="coerce")
    g = df.groupby(["Aryl SMILES", "Amine SMILES"])["_y"].agg(["max", "min"]).reset_index()
    all0 = g[g["max"] == 0]
    contrast = g[(g["min"] == 0) & (g["max"] > 0)]
    neg_pairs = []
    for aryl, amine in all0[["Aryl SMILES", "Amine SMILES"]].head(NEG_CAP) \
            .itertuples(index=False, name=None):
        sub = df[(df["Aryl SMILES"] == aryl) & (df["Amine SMILES"] == amine)]
        neg_pairs.append((aryl, amine, sub["Product SMILES"].iloc[0]))
    pos_rows = df[df["_y"] > 0].merge(contrast[["Aryl SMILES", "Amine SMILES"]],
                                      on=["Aryl SMILES", "Amine SMILES"], how="inner")
    pos_rows = list(pos_rows[["Aryl SMILES", "Amine SMILES", "Product SMILES"]]
                    .head(POS_CAP).itertuples(index=False, name=None))
    print("=" * 96)
    print(f"HTE 接入后复测：NEG {len(neg_pairs):,} 对 / POS {len(pos_rows):,} 条")
    print("=" * 96, flush=True)

    results = [run_config("baseline", None, 5, neg_pairs, pos_rows, t0),
               run_config("mined_K5", TMPL, 5, neg_pairs, pos_rows, t0),
               run_config("mined_K1", TMPL, 1, neg_pairs, pos_rows, t0),
               # ★ 第十七轮新增：K1 + 非孤儿规则（自抽模板只能丰富已被门控认可的对）
               run_config("mined_K1_非孤儿", TMPL, 1, neg_pairs, pos_rows, t0, gate_extra=True)]
    b = results[0]
    print()
    print("=" * 96)
    print("对比（相对 baseline）")
    print("=" * 96)
    for r in results:
        d_neg = r["neg_false_positive_rate"] - b["neg_false_positive_rate"]
        d_pos = r["pos_recall"] - b["pos_recall"]
        print(f"  {r['config']:<14} 模板 {r['n_extra_compiled']:>4} | "
              f"假阳性 {b['neg_false_positive_rate']:.1%} -> {r['neg_false_positive_rate']:.1%} "
              f"({d_neg:+.1%}) | 召回 {b['pos_recall']:.1%} -> {r['pos_recall']:.1%} "
              f"({d_pos:+.1%}) | 负例产物 {r['neg_products_per_pair']:.2f}/对 "
              f"(自抽 {r['neg_extra_products_per_pair']:.2f})")
    payload = {"scratch": "接入 ORD 自抽模板后，HTE 假阳性/召回复测",
               "neg_cap": NEG_CAP, "pos_cap": POS_CAP,
               "results": results,
               "delta_vs_baseline": {
                   r["config"]: {
                       "d_false_positive_rate": r["neg_false_positive_rate"]
                       - b["neg_false_positive_rate"],
                       "d_recall": r["pos_recall"] - b["pos_recall"],
                       "neg_products_per_pair": r["neg_products_per_pair"],
                       "neg_extra_only_rate": r["neg_extra_only_rate"]}
                   for r in results},
               "seconds": round(time.time() - t0, 1)}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n结果 -> {OUT.name}  总耗时 {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
