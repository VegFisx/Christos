# -*- coding: utf-8 -*-
"""一次性探针（只读）：方剂库的结构 + 药材名能不能对上 tcm.db。"""
from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FJ = Path(r"D:\TCMAI\data\formula_db.json")
TCM = r"D:\TCMAI\tcm.db"


def main() -> None:
    d = json.loads(FJ.read_text(encoding="utf-8"))
    print("方剂总数 =", len(d))
    k0 = next(iter(d))
    e = d[k0][0]
    print("样例方剂：%s（%d 条记录）" % (k0, len(d[k0])))
    print("  字段 =", list(e.keys()))
    for kk, vv in e.items():
        s = str(vv)
        print("    %-14s %s" % (kk, s[:150].replace("\n", " ")))
    print()
    n_multi = sum(1 for v in d.values() if len(v) > 1)
    print("一个名字对应多条记录的方剂 = %d" % n_multi)
    print()

    # 找"组成"字段：看哪个键在大多数记录里像药材列表
    keys = Counter()
    for v in d.values():
        for rec in v:
            keys.update(rec.keys())
    print("字段出现次数：")
    for kk, n in keys.most_common():
        print("   %-16s %d" % (kk, n))

    # 组成字段 = peifang（逗号分隔的中文串）
    cand = "peifang"
    print()
    print("最像「药材名」的字段 =", cand)
    if cand:
        samples = []
        for v in d.values():
            for rec in v:
                x = rec.get(cand)
                if x:
                    samples.append(x)
        print("  非空记录 =", len(samples), "/", sum(len(v) for v in d.values()))
        print("  样例 =", str(samples[0])[:200])
        import re as _re
        def _split_pf(x):
            return [t.strip() for t in _re.split(r"[，,、;；]", str(x or "")) if t.strip()]
        lens = [len(_split_pf(x)) for x in samples]
        print("  味数分布：min %d / 中位 %d / max %d"
              % (min(lens), sorted(lens)[len(lens) // 2], max(lens)))
        # 能否对上 tcm.db 的 name_cn
        c = sqlite3.connect("file:" + TCM.replace("\\", "/") + "?mode=ro", uri=True)
        names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
        c.close()
        flat = []
        for x in samples:
            flat.extend(_split_pf(x))
        flat = [str(t).strip() for t in flat if str(t).strip()]
        ok = sum(1 for t in flat if t in names)
        print("  药材名总数 %d，能在 tcm.db 精确命中 %d（%.1f%%）"
              % (len(flat), ok, 100.0 * ok / max(1, len(flat))))
        miss = [t for t in flat if t not in names]
        print("  未命中样例 =", miss[:12])
        print()
        print("单方平均味数 %.1f；味数最多的方剂：" % (sum(lens) / max(1, len(lens))))
        order = sorted(zip(lens, samples), key=lambda t: -t[0])[:3]
        for n, x in order:
            print("   %d 味：%s" % (n, str(x)[:120]))
        print()
        cats = Counter(rec.get("category") for v in d.values() for rec in v)
        print("category 分布（前 6）：", cats.most_common(6))
        src = Counter(rec.get("chuchu") for v in d.values() for rec in v)
        print("chuchu 分布（前 6）：", src.most_common(6))


if __name__ == "__main__":
    main()
