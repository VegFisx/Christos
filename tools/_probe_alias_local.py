# -*- coding: utf-8 -*-
"""一次性探针（只读）：本地 herb_aliases_map.json 的质量与覆盖。

Q1 多少条、值能不能对上 tcm.db 的药材名
Q2 与 herbs.alias 列（12,285 条）的重叠
Q3 拿它去解药典组成里**原来对不上**的那些名字，能救回多少
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "sources"))
AMAP = Path(r"D:\TCMAI\data\herb_aliases_map.json")
TCM = "file:D:/TCMAI/tcm.db?mode=ro"


def main() -> None:
    m = json.loads(AMAP.read_text(encoding="utf-8"))
    print("[Q1] 本地别名表 = %d 条" % len(m))
    c = sqlite3.connect(TCM, uri=True)
    names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
    vals = [str(v) for v in m.values()]
    hit = sum(1 for v in vals if v in names)
    print("     值能在 tcm.db 精确命中 = %d（%.1f%%）"
          % (hit, 100.0 * hit / max(1, len(vals))))
    bad = [v for v in vals if v not in names]
    from collections import Counter
    print("     未命中 Top 10：", Counter(bad).most_common(10))
    # 反向：tcm.db 的药材有没有出现在这张表的值里
    print("     tcm.db 药材名被这张表覆盖到的 = %d / %d"
          % (len(set(vals) & names), len(names)))

    print("[Q2] 与 herbs.alias 列对比")
    db_alias = {}
    for cn, al in c.execute("SELECT name_cn, COALESCE(alias,'') FROM herbs"):
        for a in str(al).replace("；", ";").replace("、", ";").replace(",", ";").split(";"):
            a = a.strip()
            if a:
                db_alias.setdefault(a, cn)
    print("     herbs.alias 展开后 = %d 条" % len(db_alias))
    both = set(m) & set(db_alias)
    print("     两表别名交集 = %d ｜ 本地独有 = %d ｜ herbs.alias 独有 = %d"
          % (len(both), len(set(m) - set(db_alias)), len(set(db_alias) - set(m))))
    # 同名别名指向不同正名 → 冲突
    conf = [k for k in both if str(m[k]) != db_alias[k]]
    print("     ★ 指向不一致的 = %d，样例：%s"
          % (len(conf), [(k, m[k], db_alias[k]) for k in conf[:5]]))
    c.close()

    print("[Q3] 用本地别名表去解药典组成里原来对不上的名字")
    import formula as F
    ov = F._overlay()
    dn, da = F._names_alias()
    still, fixed = {}, {}
    for nm, e in ov.items():
        for comp in (e.get("组成") or []):
            t = F._clean_chp_herb(comp.get("herb"))
            if not t:
                continue
            if F._resolve_one(t, dn, da):
                continue
            got = m.get(t)
            if got and got in dn:
                fixed[t] = got
            else:
                still[t] = still.get(t, 0) + 1
    print("     靠本地别名表能救回 = %d 个不同名字" % len(fixed))
    print("     救回样例：", list(fixed.items())[:15])
    print("     仍对不上 Top 12：",
          sorted(still.items(), key=lambda x: -x[1])[:12])


if __name__ == "__main__":
    main()
