# -*- coding: utf-8 -*-
r"""
一次性探针（H1）：先看清 formula_db.json 与 formula_db_api_only.json 的真实形状。
只打印原始形状与少量样例，不做任何判定。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FJ = Path(r"D:\TCMAI\data\formula_db.json")
API = Path(r"D:\TCMAI\data\formula_db_api_only.json")


def load(p: Path):
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    db = load(FJ)
    print("=" * 100)
    print("formula_db.json：%d 个方名" % len(db))
    n_rec = sum(len(v) for v in db.values())
    print("记录总数 = %d（平均每方 %.2f 条）" % (n_rec, n_rec / max(1, len(db))))

    # 1) 字段名统计
    keys = Counter()
    for v in db.values():
        for r in v:
            keys[tuple(sorted(r.keys()))] += 1
    print("\n【字段组合】")
    for kk, n in keys.most_common():
        print("  %6d 条  %s" % (n, list(kk)))

    # 2) category 取值分布
    cat = Counter()
    for v in db.values():
        for r in v:
            cat[repr(r.get("category"))] += 1
    print("\n【category 取值分布】")
    for kk, n in cat.most_common(20):
        print("  %6d 条  %s" % (n, kk))

    # 3) 逐字段值样例：每个 category 各取一条
    print("\n【样例（每个 category 一条）】")
    seen = set()
    for name, v in db.items():
        for r in v:
            c = repr(r.get("category"))
            if c in seen:
                continue
            seen.add(c)
            print("-" * 100)
            print("方名:", name, "｜ category =", c)
            for kk, vv in r.items():
                s = str(vv)
                print("   %-10s %s" % (kk, s[:180].replace("\n", "\\n")))
            if len(seen) >= 8:
                break
        if len(seen) >= 8:
            break

    # 4) api_only 文件形状
    print("\n" + "=" * 100)
    api = load(API)
    n_api = sum(len(v) for v in api.values()) if isinstance(api, dict) else len(api)
    print("formula_db_api_only.json：类型=%s 方名数=%s 记录数=%s"
          % (type(api).__name__, len(api) if hasattr(api, "__len__") else "-", n_api))
    if isinstance(api, dict):
        k0 = next(iter(api))
        v0 = api[k0]
        print("样例键:", k0, "｜ 值的类型:", type(v0).__name__)
        if isinstance(v0, list) and v0:
            print("样例记录字段:", list(v0[0].keys()))
            for kk, vv in v0[0].items():
                print("   %-10s %s" % (kk, str(vv)[:180].replace("\n", "\\n")))

    # 5) 两份文件的方名交集
    if isinstance(api, dict):
        a, b = set(db), set(api)
        print("\n交集方名 = %d ｜ 仅在主库 = %d ｜ 仅在 api_only = %d"
              % (len(a & b), len(a - b), len(b - a)))


if __name__ == "__main__":
    main()
