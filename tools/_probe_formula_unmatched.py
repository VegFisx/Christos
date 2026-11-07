# -*- coding: utf-8 -*-
r"""一次性探针：方剂/药典方组成里**对不上库**的药材 token 有多少、涉及多少个不同名字。

用途：给"中文名→物种桥"定一个**真正有收益**的优先集（而不是 5,982 个冷门名全跑）。
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = r"D:\ProgramData\DSHNS\chemreact-staging"
sys.path.insert(0, STAGE + r"\sources")
import formula as F                                        # noqa: E402

c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
names = {r[0] for r in c.execute("SELECT name_cn FROM herbs")}
alias_elems = set()
for (al,) in c.execute("SELECT alias FROM herbs WHERE alias IS NOT NULL"):
    for x in str(al).replace("；", ";").replace("，", ";").replace(",", ";").split(";"):
        x = x.strip()
        if x:
            alias_elems.add(x)
c.close()

bad = Counter()
n_tok = n_bad = 0
db = F._load()
for nm, recs in db.items():
    for r in recs:
        for tok in F.split_ingredients(str(r.get("peifang") or "")):
            t = F.clean_token(tok)
            if not t:
                continue
            n_tok += 1
            if t in names or t in alias_elems:
                continue
            if F._resolve_one(t, names, {}) is not None:
                continue
            n_bad += 1
            bad[t] += 1

print("方剂组成 token 总数 = %d ｜ 对不上 = %d（%.1f%%）｜ 不同名字 = %d"
      % (n_tok, n_bad, 100.0 * n_bad / max(1, n_tok), len(bad)))
print("Top 30 对不上的名字：")
for k, v in bad.most_common(30):
    print("   %4d  %s" % (v, k))

import json as _json
out = STAGE + r"\data\formula_unmatched_tokens.json"
open(out, "w", encoding="utf-8").write(_json.dumps(
    {"n_tokens": n_tok, "n_unmatched": n_bad, "counts": dict(bad)},
    ensure_ascii=False, indent=1))
tot = sum(bad.values())
print()
print("覆盖率曲线（按出现次数从高到低取前 K 个名字）：")
acc = 0
for i, (k, v) in enumerate(bad.most_common(), 1):
    acc += v
    if i in (25, 50, 100, 200, 300, 500, 1000):
        print("   Top %-5d 名字 → 覆盖对不上 token 的 %.1f%%（%d/%d）"
              % (i, 100.0 * acc / tot, acc, tot))
print("   -> %s" % out)
