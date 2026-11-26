# -*- coding: utf-8 -*-
"""跑 TCM 之外的通用有机反应覆盖探针（USPTO-50k 官方 test 分层样本）。

预注册输入：data/holdout_general_organic_20261123.json
配置：
  strict     = curated 文件级加载，只放 provenance=cited/secondary
  exploratory= curated 文件级加载，允许 unvalidated
extra/mono/base/coverage/stereo 全关；条件门控关，只测规则可达性。
命中：任一主产物/伴生产物 InChIKey 前 14 位等于目标；exact canonical 为次要指标。

用法：
    python tools\\run_general_holdout.py
"""
from __future__ import annotations

import argparse
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

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem
import query_base as qb
import reaction_paths as rp

SRC = ROOT / "data" / "holdout_general_organic_20261123.json"
OUT = ROOT / "reports" / "general_organic_20261123.json"
CONFIGS = {
    "strict": False,
    "exploratory": True,
}


def canon(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""


def key(s):
    m = Chem.MolFromSmiles(s or "")
    if m is None:
        return ""
    try:
        from rdkit.Chem import inchi
        return inchi.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def run_case(case, allow_unvalidated):
    seeds = [("r%d" % (i + 1), s, "USPTO-50K official test")
             for i, s in enumerate(case["reactants"])]
    spec = qb.RunSpec(
        seeds=seeds, cond_name="煎煮", rounds=1, max_pairs=200,
        max_products_per_pair=64,
        use_curated_templates=True,
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        allow_unvalidated=bool(allow_unvalidated),
        strict_redox_gate=False, gate_conditions=False,
    )
    t0 = time.time()
    inv = qb.build_inventory(spec, score=False, use_cache=False)
    hops = rp.expand_co_products(rp.hops_from_paths(inv.paths))
    secs = round(time.time() - t0, 2)

    products = set()
    hit_rules = set()
    target_key = key(case["product"])
    target_canon = canon(case["product"])
    exact = False
    skeleton = False
    for h in hops:
        frags = [h.product] + (h.co_products or "").split("|")
        for f in frags:
            c = canon(f)
            if not c:
                continue
            products.add(c)
            if c == target_canon:
                exact = True
            if target_key and key(c) == target_key:
                skeleton = True
                if h.rule:
                    hit_rules.add(h.rule)
    return {
        "id": case["id"],
        "class": case["class"],
        "n_reactants": case["n_reactants"],
        "n_hops": len(hops),
        "n_products": len(products),
        "exact": exact,
        "skeleton": skeleton,
        "hit_rules": sorted(hit_rules),
        "seconds": secs,
        "engine_notes": list(getattr(inv.stats, "engine_notes", []) or []),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    src = Path(a.holdout).resolve()
    out_path = Path(a.out).resolve()
    data = json.loads(src.read_text(encoding="utf-8"))
    cases = data["cases"]
    results = {}
    for name, allow in CONFIGS.items():
        print("config", name, "allow_unvalidated=", allow, flush=True)
        rows = []
        for i, case in enumerate(cases, 1):
            try:
                row = run_case(case, allow)
            except Exception as ex:
                row = {"id": case["id"], "class": case["class"],
                       "error": "%s: %s" % (type(ex).__name__, ex),
                       "skeleton": False, "exact": False,
                       "hit_rules": [], "n_products": 0, "n_hops": 0,
                       "seconds": 0}
            rows.append(row)
            if not a.quiet:
                flag = "HIT" if row.get("skeleton") else "."
                print(" %2d/%2d %-10s %-42s %s p=%s" %
                      (i, len(cases), "class " + row.get("class", "?"),
                       row.get("id", ""), flag, row.get("n_products", 0)), flush=True)
        results[name] = rows

    summary = {}
    for name, rows in results.items():
        n = len(rows)
        sk = sum(bool(r.get("skeleton")) for r in rows)
        ex = sum(bool(r.get("exact")) for r in rows)
        err = sum("error" in r for r in rows)
        by_class = {}
        for cls in sorted({r.get("class") for r in rows},
                          key=lambda x: int(x) if str(x).isdigit() else 999):
            rr = [r for r in rows if r.get("class") == cls]
            by_class[cls] = {
                "n": len(rr),
                "skeleton": sum(bool(r.get("skeleton")) for r in rr),
                "exact": sum(bool(r.get("exact")) for r in rr),
            }
        summary[name] = {"n": n, "skeleton": sk, "exact": ex,
                         "errors": err, "by_class": by_class}

    # 探索集是严格集的超集；命中不应减少。
    nonmono = []
    for a, b in zip(results["strict"], results["exploratory"]):
        if a.get("skeleton") and not b.get("skeleton"):
            nonmono.append(a["id"])

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(src.relative_to(ROOT)),
        "configs": CONFIGS,
        "summary": summary,
        "nonmonotonic": nonmono,
        "results": results,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsummary")
    for name, s in summary.items():
        print(" ", name, "skeleton=%d/%d exact=%d/%d errors=%d"
              % (s["skeleton"], s["n"], s["exact"], s["n"], s["errors"]))
        for cls, v in s["by_class"].items():
            print("   class", cls, "%d/%d skeleton" % (v["skeleton"], v["n"]))
    print("nonmonotonic", nonmono)
    print("written", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
