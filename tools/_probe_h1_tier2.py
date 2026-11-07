# -*- coding: utf-8 -*-
r"""
一次性探针（H1 第二步）：chuchu 字段的取值分布 —— 这是打 tier 的判据来源。
先打印原始值，再谈规则。
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
CHP = Path(r"D:\ProgramData\DSHNS\chemreact-staging\data\chp_formulas.json")


def main() -> None:
    db = json.loads(FJ.read_text(encoding="utf-8"))
    print("=" * 100)
    print("【A】按 category 分组的 chuchu 取值分布（Top 30，逐条打印原始值）")
    grp = {}
    for name, v in db.items():
        for r in v:
            c = r.get("category")
            grp.setdefault(c, Counter())[str(r.get("chuchu"))[:60]] += 1
    for c, cnt in grp.items():
        print("-" * 100)
        print("category = %r ｜ 记录 %d 条 ｜ 不同 chuchu 取值 %d 个"
              % (c, sum(cnt.values()), len(cnt)))
        for val, n in cnt.most_common(30):
            print("    %6d  %s" % (n, val))

    print()
    print("=" * 100)
    print("【B】API 批（category=None）里 chuchu 的形态")
    api_recs = [r for v in db.values() for r in v if r.get("category") is None]
    forms = Counter()
    for r in api_recs:
        s = (r.get("chuchu") or "").strip()
        if not s:
            forms["（空）"] += 1
        elif s.startswith("《") and ("》" in s):
            forms["《书名》"] += 1
        else:
            forms["其它形态：" + s[:40]] += 1
    for k, n in forms.most_common(20):
        print("    %6d  %s" % (n, k))

    print()
    print("=" * 100)
    print("【C】api_only 文件：非空条目数 / 空条目数")
    api = json.loads(API.read_text(encoding="utf-8"))
    ne = sum(1 for v in api.values() if v)
    empty = len(api) - ne
    n_rec = sum(len(v) for v in api.values())
    same_name = sum(1 for k, v in api.items() if v and set(x["name"] for x in v) == {k})
    print("    非空方名 = %d ｜ 空方名 = %d ｜ 记录数 = %d ｜ 记录 name 与键同名 = %d"
          % (ne, empty, n_rec, same_name))

    print()
    print("=" * 100)
    print("【D】药典 overlay 的 1,526 方，在 formula_db.json 里的覆盖情况")
    chp = json.loads(CHP.read_text(encoding="utf-8"))
    names_db = set(db)
    hit = [k for k in chp if k in names_db]
    print("    药典方名 = %d ｜ 在 formula_db.json 里有同名键 = %d" % (len(chp), len(hit)))
    c2 = Counter()
    for k in hit:
        for r in db[k]:
            c2[str(r.get("chuchu"))[:40]] += 1
    print("    这些同名键的记录 chuchu 分布：")
    for val, n in c2.most_common(10):
        print("      %6d  %s" % (n, val))


if __name__ == "__main__":
    main()
