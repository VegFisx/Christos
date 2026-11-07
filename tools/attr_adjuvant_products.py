"""量化「炮制辅料到底带来了多少产物」：同一种子集，跑两遍（有辅料 / 无辅料），做差集。

为什么需要它：`chemreact.py` 里 `n_products_from_adjuvant` 只看台账 source_herb 是否为
「辅料:」，但双底物规则的台账只记主底物，辅料在 partner 一侧 → 永远算 0。这个工具用
「有/无辅料两次独立运行取差集」给出可信数字，不依赖台账的归因字段。

用法：
    python -I tools/attr_adjuvant_products.py --herb 甘草 --method 醋炙 --top 6
    python -I tools/attr_adjuvant_products.py --herb 甘草 --method 蜜炙 --top 6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
for _sub in ("core", "conditions", "sources", "tools"):
    _p = str(_ROOT / _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import paozhi_adjuvants as PA  # noqa: E402
import validate_formula_decoction as F  # noqa: E402
from herb import compounds_of_herb  # noqa: E402


def seeds_of(herb: str, top: int):
    cs = compounds_of_herb(herb, limit=top)
    return [{"name": c.name or getattr(c, "_iid", "?"), "smiles": c.smiles, "herb": herb}
            for c in cs if getattr(c, "smiles", "")]


def products(hops):
    out = {}
    for h in hops:
        key = h.product
        out.setdefault(key, h)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default="甘草")
    ap.add_argument("--method", default="醋炙")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--max-pairs", type=int, default=400)
    args = ap.parse_args()

    base = seeds_of(args.herb, args.top)
    adj = [c for c in PA.describe(args.method) if c.get("smiles")]
    with_adj = base + [{"name": c.get("name") or "辅料", "smiles": c["smiles"],
                        "herb": "辅料:%s" % c.get("adjuvant", "")} for c in adj]

    t0 = time.time()
    hops_base, s1 = F.run_batch(base, "炮制·%s" % args.method, max_pairs=args.max_pairs)
    hops_adj, s2 = F.run_batch(with_adj, "炮制·%s" % args.method, max_pairs=args.max_pairs)
    pb, pa = products(hops_base), products(hops_adj)
    only = {k: v for k, v in pa.items() if k not in pb}

    from collections import Counter
    rules = Counter(v.rule for v in only.values())
    examples = [{"formula": v.product_formula, "rule": v.rule,
                 "source": v.source_name} for v in list(only.values())[:5]]
    print("== %s / %s ==" % (args.herb, args.method))
    print("  无辅料：%d 产物（%s s）· 有辅料：%d 产物（%s s）"
          % (len(pb), s1, len(pa), s2))
    print("  ★ 只能由辅料带来的产物：%d 个" % len(only))
    print("     规则分布：%s" % (rules.most_common(6) or "无"))
    for e in examples:
        print("     %s  ← %s（来源 %s）" % (e["formula"], e["rule"], e["source"]))

    dst = _ROOT / "reports" / ("adjuvant_attr_%s_%s.json" % (args.herb, args.method))
    dst.write_text(json.dumps({"herb": args.herb, "method": args.method,
                               "n_base": len(pb), "n_with_adj": len(pa),
                               "n_only_adjuvant": len(only),
                               "rules": dict(rules), "examples": examples,
                               "seconds": round(time.time() - t0, 1)},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print("  写出 %s" % dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
