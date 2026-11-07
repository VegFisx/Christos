# -*- coding: utf-8 -*-
r"""第 2 件：零产率（"明确没发生"）数据能不能**校准方向判据**？—— 先测它有没有信号。

## 为什么先测"有没有信号"
"用负例校准方向"听起来对，但成立的前提是：
**同一反应类型在不同溶剂/温度下，零产率率真的不一样。**
如果各个溶剂桶的零产率率基本一样（或者样本太少），那这份数据**校准不了方向** ——
那就该老实说"不行"，而不是硬造一张表。

## 口径（先定死）
* 数据 1（ORD 侧）：`reports/negative_examples.jsonl`（404 条真实 `PERCENTYIELD==0` +
  449 条 notes 严格短语）+ `negative_yield_zero.jsonl`
  这些记录**没有反应类型标签**，所以只能看"整体 + 溶剂桶"的分布。
* 数据 2（HTE 侧，带类型）：`reports/hte_negatives.jsonl`（10,696 条 `NEG_COND`，产率 0）
  —— 但它**只有一个反应类（Buchwald-Hartwig）**，所以只能看"同一类里溶剂差异"。
* 指标：
  - ORD：负例的溶剂桶分布 vs ORD 全量成功记录的溶剂桶分布（有偏就说明溶剂与"没发生"相关）
  - HTE：同一 aryl/amine 组内，零产率记录 vs 有产率记录的**溶剂分布差异**
    （用组内对照，排除底物差异）
* 输出：`reports/zero_yield_calibration_probe.json`

用法:
    & $py -u tools\probe_zero_yield_calibration.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
REP = STAGE / "reports"
OUT = REP / "zero_yield_calibration_probe.json"

WATER = ("water", "aqueous", "buffer", "h2o")
NONWATER = ("ethanol", "methanol", "dmso", "dmf", "thf", "dcm", "dichloromethane",
            "toluene", "acetonitrile", "meoh", "etoh", "ipa", "isopropanol",
            "chloroform", "ether", "dioxane", "acetone", "t-amoh", "dma",
            "2-me-thf", "dme", "tbuoh", "mtbe", "hexane", "cyclohexane")


def bucket(s: str) -> str:
    t = str(s or "").strip().lower()
    if not t:
        return "unknown"
    for w in WATER:
        if w in t:
            return "water_like"
    for w in NONWATER:
        if w in t:
            return "nonwater"
    return "unknown"


def probe_ord_zero_yield():
    """ORD 侧：负例的溶剂分布 vs 成功记录的溶剂分布。"""
    out = {"files": {}}
    # ① negative_examples.jsonl（404 条真实零产率 + notes 短语）
    p = REP / "negative_examples.jsonl"
    n = 0
    solv = Counter()
    kinds = Counter()
    has_type = 0
    if p.exists():
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                n += 1
                kinds[str(r.get("kind") or r.get("route") or "?")] += 1
                sv = r.get("solvents") or r.get("solvent_names") or r.get("solvent")
                if isinstance(sv, list):
                    for s in sv:
                        solv[bucket(s)] += 1
                elif sv:
                    solv[bucket(sv)] += 1
                if r.get("reaction_class") or r.get("classes"):
                    has_type += 1
    out["files"]["negative_examples.jsonl"] = {
        "n": n, "by_kind": dict(kinds), "solvent_buckets": dict(solv),
        "n_with_reaction_type": has_type}
    # ② negative_yield_zero.jsonl
    for name in ("negative_yield_zero.jsonl", "negative_clean.jsonl"):
        p2 = REP / name
        if not p2.exists():
            continue
        n2 = 0
        sv2 = Counter()
        keys = set()
        with open(p2, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                n2 += 1
                keys |= set(r.keys())
                sv = r.get("solvents") or r.get("solvent_names") or r.get("solvent")
                if isinstance(sv, list):
                    for s in sv:
                        sv2[bucket(s)] += 1
                elif sv:
                    sv2[bucket(sv)] += 1
        out["files"][name] = {"n": n2, "solvent_buckets": dict(sv2),
                              "fields": sorted(keys)}
    return out


def probe_hte_within_group():
    """HTE 侧：同一 (aryl, amine) 组内，零产率 vs 有产率 的溶剂分布差异。"""
    p = (STAGE / "data" / "external" / "bh-hte-ood"
         / "schwallergroup-bh-hte-ood-a277041" / "data"
         / "BH_HTE_Curated_Dataset_v20260219.csv")
    groups = defaultdict(lambda: {"zero": Counter(), "pos": Counter()})
    with open(p, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("Aryl SMILES", "")).strip(),
                   str(row.get("Amine SMILES", "")).strip())
            if not key[0] or not key[1]:
                continue
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            b = bucket(row.get("Solvent Name", ""))
            (groups[key]["zero"] if y == 0.0 else groups[key]["pos"])[b] += 1
    # 只保留两类都有的组（组内对照）
    both = {k: v for k, v in groups.items()
            if sum(v["zero"].values()) and sum(v["pos"].values())}
    zt = Counter()
    pt = Counter()
    for v in both.values():
        zt += v["zero"]
        pt += v["pos"]
    return {"n_groups_total": len(groups), "n_groups_with_both": len(both),
            "zero_records_by_bucket": dict(zt), "pos_records_by_bucket": dict(pt),
            "zero_rate_by_bucket": {
                b: round(zt[b] / (zt[b] + pt[b]), 4)
                for b in sorted(set(zt) | set(pt)) if (zt[b] + pt[b]) > 0}}


def main() -> int:
    print("=" * 92)
    print("第 2 件：零产率数据有没有校准方向的信号？")
    print("=" * 92)
    ord_side = probe_ord_zero_yield()
    hte_side = probe_hte_within_group()

    print("\n① ORD 侧负例（『明确没发生』的记录）")
    for name, d in ord_side["files"].items():
        print(f"   {name}: {d['n']:,} 条")
        if d.get("by_kind"):
            print(f"      来源路线: {d['by_kind']}")
        print(f"      溶剂桶: {d.get('solvent_buckets')}")
        if "n_with_reaction_type" in d:
            print(f"      带反应类型的条目: {d['n_with_reaction_type']}")
        if d.get("fields"):
            print(f"      字段: {d['fields'][:12]}")

    print("\n② HTE 侧（带反应类型，但只有一类）")
    print(f"   组数 {hte_side['n_groups_total']:,}，其中"
          f"『组内既有零产率又有正产率』的组 {hte_side['n_groups_with_both']:,}")
    print(f"   零产率记录的溶剂分布: {hte_side['zero_records_by_bucket']}")
    print(f"   正产率记录的溶剂分布: {hte_side['pos_records_by_bucket']}")
    print("   ★ 各溶剂桶的零产率率（组内对照）：")
    for b, r in sorted(hte_side["zero_rate_by_bucket"].items(), key=lambda kv: -kv[1]):
        print(f"      {b:<12} {r:.1%}")

    payload = {"what": "零产率数据能否校准方向判据（先测有没有信号）",
               "ord_side": ord_side, "hte_side": hte_side}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
