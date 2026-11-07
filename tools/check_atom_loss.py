#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查「一层反应之后原子凭空消失」的台账行（第八十九轮后续，问题 19）。

背景
----
2026-11-04 追三条「整层丢立体」的跳时发现：问题不在立体，而在模板本身。
ORD mined 模板只记录论文里写出来的主产物，模板 SMARTS 没覆盖到的部分会被
直接删掉，于是台账上出现 ``C36H38O16`` → ``C10H12O3`` 这种一步丢掉 26 个碳、
13 个氧的反应。引擎不报错，台账也看不出异常——所以需要一个观测量把它标出来。

口径（行级，不是跳级）
----------------------
守恒率 = (主产物 + 伴生产物) 重原子数 / 底物重原子数

只看主产物会把每一处水解都误标：水解是「一分为二」，主产物常常只是一半
（糖，或苷元）。把 ``co_products``（``|`` 分隔）加进来，才是「这一步到底
留没留下底物里的原子」。

* ``< --min-keep``（默认 0.7）= 疑似模板删原子，列出来。
* ``> 1`` 正常（加成、缩合、两底物成键），不报。
* 只做观测：不改产物、不过滤、不排序。

用法
----
    python tools\\check_atom_loss.py <输出目录 或 台账.csv> [--min-keep 0.7] [--top 15] [-o json]

按规则汇总「低守恒行数 / 该类总行数」，降序排列。``mined_*``、``smartreact_*``
最可能是来源；curated 规则出现低守恒，通常说明规则 SMARTS 写漏了原子。
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
for _sub in ("core", "conditions", "tools"):
    _p = _ROOT / _sub
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import reaction_paths as rp  # noqa: E402


def _pick_csv(target: Path) -> Path:
    if target.is_file():
        return target
    cands = sorted(target.glob("*.csv"))
    if not cands:
        raise SystemExit("目录里没有 *.csv 台账：%s" % target)
    return max(cands, key=lambda p: p.stat().st_size)


def main() -> int:
    ap = argparse.ArgumentParser(description="标出台账里原子守恒率过低的行")
    ap.add_argument("target", help="输出目录，或直接给台账 csv")
    ap.add_argument("--min-keep", type=float, default=0.7,
                    help="守恒率低于此值算「疑似删原子」（默认 0.7）")
    ap.add_argument("--top", type=int, default=15, help="每张表最多列多少行（默认 15）")
    ap.add_argument("-o", "--json", dest="json_out", default="", help="把完整结果写成 json")
    a = ap.parse_args()

    csv_path = _pick_csv(Path(a.target))
    per_rule = defaultdict(lambda: {"n": 0, "low": 0, "keeps": [], "ex": []})
    low_all = []
    n_rows = 0
    judged = 0
    if not csv_path.exists():
        raise SystemExit("找不到台账：%s" % csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            n_rows += 1
            keep = rp.atom_conservation(row.get("source_smiles", ""),
                                        row.get("product_smiles", ""),
                                        row.get("co_products", ""),
                                        row.get("partner_smiles", ""))
            if keep is None:
                continue
            judged += 1
            rule = row.get("rule_name", "") or "?"
            b = per_rule[rule]
            b["n"] += 1
            b["keeps"].append(keep)
            if keep < a.min_keep:
                b["low"] += 1
                sf = rp.formula_of(row.get("source_smiles", ""))
                pf = rp.formula_of(row.get("product_smiles", ""))
                if len(b["ex"]) < 3:
                    b["ex"].append((sf or "?", pf or "?", round(keep, 3)))
                low_all.append({
                    "rule": rule, "round": row.get("round", ""), "keep": round(keep, 3),
                    "source_formula": sf, "product_formula": pf,
                    "product_smiles": row.get("product_smiles", ""),
                    "co_products": row.get("co_products", ""),
                })

    if not n_rows:
        print("台账是空的：%s" % csv_path)
        return 1

    rows = sorted(per_rule.items(), key=lambda kv: (-kv[1]["low"], kv[0]))
    print("台账：%s" % csv_path.name)
    print("行数 %d（可判 %d）· 守恒率 < %.2f 的行 %d 条 · 涉及规则 %d 类"
          % (n_rows, judged, a.min_keep, len(low_all),
             sum(1 for v in per_rule.values() if v["low"])))
    print("")
    print("%-40s %7s %6s %9s  %s" % ("规则", "低守恒", "总行", "中位守恒", "典型分子式变化"))
    print("-" * 104)
    for rule, v in rows[:a.top]:
        med = statistics.median(v["keeps"])
        ex = v["ex"][0] if v["ex"] else ("", "", "")
        print("%-40s %7d %6d %9.3f  %s -> %s" % (rule[:40], v["low"], v["n"], med, ex[0], ex[1]))
    if len(rows) > a.top:
        print("… 另有 %d 类规则（用 --top 调整）" % (len(rows) - a.top))

    mined = sum(v["low"] for k, v in per_rule.items() if k.startswith(("mined", "smartreact")))
    curated = sum(v["low"] for k, v in per_rule.items() if not k.startswith(("mined", "smartreact")))
    print("")
    print("来源拆分：mined/smartreact 模板 %d 条 · curated 规则 %d 条" % (mined, curated))
    if curated:
        print("注意：curated 规则出现低守恒，多数仍是「主产物只是一半」的拆分类反应；"
              "若同时伴生产物也补不回来，才回查 rules.json 的 SMARTS。")

    if a.json_out:
        out = Path(a.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "ledger": str(csv_path),
            "min_keep": a.min_keep,
            "n_rows": n_rows,
            "n_judged": judged,
            "n_low": len(low_all),
            "by_rule": {k: {"n": v["n"], "low": v["low"],
                            "median_keep": round(statistics.median(v["keeps"]), 4)}
                        for k, v in rows},
            "low_rows": low_all[:500],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已写 %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
