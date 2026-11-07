# -*- coding: utf-8 -*-
"""一次性：验证第三十轮新增（相似度 / 聚合 / 查询日志）。只打印摘要。"""
from __future__ import annotations

import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb  # noqa: E402


def main() -> int:
    inv = qb.load_inventory()
    print(f"台账 {len(inv.paths)} 条路径 / {len(inv)} 个产物")

    # ---- 相似度检索 ----
    for ref, thr in (("OCc1ccccc1", 0.3), ("glycyrrhizin", 0.35)):
        t0 = time.time()
        r = qb.query_similar(inv, ref, threshold=thr, limit=5)
        dt = time.time() - t0
        print(f"\n[相似] query={ref!r} thr={thr} -> n_hits={r['n_hits']} "
              f"耗时 {dt:.2f}s fps={r['fp_stats']}")
        if r.get("error"):
            print("   error:", r["error"])
        for h in r["hits"][:5]:
            print(f"   {h['tanimoto']:.3f}  {h['formula']:<16} "
                  f"{str(h['rules'])[:28]:<30} {h['smiles'][:44]}")

    # ---- 聚合视图 ----
    a = qb.aggregate_by_rule(inv, limit=10)
    print(f"\n[聚合] 反应类型 {a['n_rules']} 类 / 出处路径 {a['n_paths']}")
    for x in a["rows"]:
        print(f"   {x['rule']:<22} products={x['products']:<5} paths={x['paths']:<5} "
              f"sources={x['sources']:<4} min_r={x['min_round']} share={x['share']:.1%}")

    # ---- 查询日志 ----
    n = qb.dump_query_log([{"ts": "selftest", "cmd": "A", "query": "C7H6O2",
                            "resolved_kind": "分子式", "found": False, "n_hits": 0}])
    st = qb.stats_of_query_log()
    print(f"\n[日志] 写入 {n} 条 -> 现有 {st['n']} 条，命中率 {st['hit_rate']:.1%}，"
          f"按入口 {st['by_cmd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
