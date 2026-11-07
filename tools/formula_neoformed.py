# -*- coding: utf-8 -*-
"""Formula-level neo-formed compound analysis.

Given a list of herbs, run one forward enumeration under a chosen condition
profile and report which products are *not* present in the input herbs.  Those
are the neo-formed compounds: species that could only appear after the herbs
were combined and heated.

This is the application layer, not a benchmark.  It answers a question a
formulation researcher actually asks: what might be created in this decoction
that is in none of its ingredients?

Usage:
    python tools/formula_neoformed.py --herbs 人参,白术,茯苓,甘草
    python tools/formula_neoformed.py --herbs ... --cond 水提 --limit 8 --rounds 2
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs",
           STAGE / "tools", STAGE / "sources", STAGE / "conditions"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402

import herb as H                 # noqa: E402
import query_base as qb          # noqa: E402

RDLogger.DisableLog("rdApp.*")


def canon(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToSmiles(m) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="方剂煎煮新生成分分析：找出只在合煎后出现的产物")
    ap.add_argument("--herbs", required=True,
                    help="药材名，逗号分隔，例如 人参,白术,茯苓,甘草")
    ap.add_argument("--cond", default="煎煮",
                    help="条件档案，默认 煎煮")
    ap.add_argument("--limit", default="all",
                    help="每味取几个成分：整数或 all")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--max-pairs", type=int, default=4000)
    ap.add_argument("--max-products", type=int, default=8)
    ap.add_argument("--fair-pairs", action="store_true")
    ap.add_argument("--rule-set", choices=("all", "tcm"), default="tcm",
                    help="all=全部模板；tcm=只保留 rules.json 里的中药规则")
    ap.add_argument("--only", choices=("all", "known", "novel"), default="all",
                    help="known=产物已在 tcm.db；novel=产物不在 tcm.db")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    names = [x.strip() for x in args.herbs.replace("，", ",").split(",")
             if x.strip()]
    if len(names) < 2:
        print("至少给两味药：多方配伍才有合煎意义")
        return 2

    limit = 200 if args.limit == "all" else int(args.limit)

    t0 = time.time()
    seeds = []
    seed_smiles = set()
    per_herb = {}
    for h in names:
        cs = H.compounds_of_herb(h, limit=limit)
        if not cs:
            print("  [warn] %s 没有取到成分" % h)
            continue
        per_herb[h] = len(cs)
        for c in cs:
            ck = canon(c.smiles)
            if not ck:
                continue
            seeds.append((c.name, c.smiles, "tcm.db:%s" % (c.herb or h)))
            seed_smiles.add(ck)

    if len(seeds) < 2:
        print("可用底物不足，无法枚举")
        return 2

    print("药材 %d 味，底物 %d 个（唯一 %d）"
          % (len(per_herb), len(seeds), len(seed_smiles)))
    for h, n in per_herb.items():
        print("  %-6s %d" % (h, n))

    spec = qb.RunSpec(
        seeds=seeds,
        cond_name=args.cond,
        rounds=args.rounds,
        max_pairs=args.max_pairs,
        max_products_per_pair=args.max_products,
        fair_pairs=args.fair_pairs,
        use_curated_templates=True,
        strict_redox_gate=True,
    )
    print("条件 %s · 轮数 %d · 对子预算 %d"
          % (args.cond, args.rounds, args.max_pairs))

    inv = qb.build_inventory(spec, score=False, use_cache=False)
    paths = inv.paths
    print("产物路径 %d 条（%.1fs）" % (len(paths), time.time() - t0))

    products = {}
    for p in paths:
        smi = p.get("product_smiles") or ""
        ck = canon(smi)
        if not ck:
            continue
        products.setdefault(ck, p)

    if args.rule_set == "tcm":
        import json as _json
        _rules = _json.loads(
            (STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
        allowed = {r["id"] for r in _rules.get("rules") or []
                   if str(r.get("status") or "active") == "active"}
        before = len(products)
        products = {k: v for k, v in products.items()
                    if (v.get("rule_name") or "") in allowed}
        print("规则集过滤（仅中药规则）：%d -> %d" % (before, len(products)))

    # 按"产物是否已在 tcm.db 里"分组：known 可查证，novel 才是真正的新成分
    import sqlite3 as _sq
    _cur = _sq.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    _cur.execute("SELECT DISTINCT inchi_key FROM compounds "
                 "WHERE inchi_key IS NOT NULL AND TRIM(inchi_key)<>''")
    lib_keys = {r[0] for r in _cur.fetchall()}
    known = {k: v for k, v in products.items()
             if (v.get("product_inchikey") or "") in lib_keys}
    novel = {k: v for k, v in products.items()
             if (v.get("product_inchikey") or "") not in lib_keys}
    print("与 tcm.db 比对：已知 %d · 库外 %d" % (len(known), len(novel)))
    if args.only == "known":
        products = known
    elif args.only == "novel":
        products = novel

    neo = {k: v for k, v in products.items() if k not in seed_smiles}
    print("唯一产物 %d 个，其中新生成分 %d 个（%.1f%%）"
          % (len(products), len(neo),
             100.0 * len(neo) / max(1, len(products))))

    if neo:
        rules = Counter((v.get("rule_name") or "?") for v in neo.values())
        print("\n新生成分的规则分布（前 12）：")
        for name, n in rules.most_common(12):
            print("  %-34s %d" % (name, n))

        pair = Counter()
        for v in neo.values():
            src = v.get("source_herb") or ""
            pair[src] += 1
        print("\n按来源药材计的新生成分（前 12）：")
        for name, n in pair.most_common(12):
            print("  %-24s %d" % (name, n))

    out = Path(args.out) if args.out else (
        STAGE / "out" / ("neoformed_%s.csv" % time.strftime("%Y%m%d-%H%M%S")))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["product_smiles", "formula", "rule_name",
                    "source_herb", "source_compound", "round",
                    "direction", "activation_why"])
        for ck, v in neo.items():
            w.writerow([ck, v.get("formula", ""), v.get("rule_name", ""),
                        v.get("source_herb", ""), v.get("source_name", ""),
                        v.get("round", ""), v.get("direction", ""),
                        v.get("activation_why", "")])
    print("\n新生成分台账 -> %s" % out)
    print("总耗时 %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
