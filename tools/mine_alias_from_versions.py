# -*- coding: utf-8 -*-
r"""从**同名方剂的多个版本**里挖「异名 → 正名」候选（第七十五轮，离线）。

思路（数据驱动，不手写）：
  * 同一个方名在不同典籍里往往只差一两味药（或只是写法不同：黄耆/黄芪、炙甘草/甘草）；
  * 对每个方名，把各版本解析后的**药材集合**列出来；
  * 若某版本里有一个 token **对不上库**，而另一版本在同一方里**多出一味**、其余集合相同，
    就把 (对不上的 token → 多出的那味) 记为一条候选，并统计它出现在多少个方名里；
  * 只产出**候选 + 证据**（出现在哪些方名、各几次），**绝不自动替换**。

产出：`data\alias_candidates_from_versions.json`
用法：``python tools\mine_alias_from_versions.py``
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = r"D:\ProgramData\DSHNS\chemreact-staging"
sys.path.insert(0, STAGE + r"\sources")
import formula as F                                        # noqa: E402


def main() -> int:
    db = F._load()
    names, alias = F._names_alias()
    votes = defaultdict(Counter)          # 对不上的 token -> Counter(正名)
    where = defaultdict(list)              # (token, 正名) -> [方名...]
    n_multi = 0
    for fname, recs in db.items():
        if len(recs) < 2:
            continue
        n_multi += 1
        per = []
        for r in recs:
            ok, bad = set(), set()
            for tok in F.split_ingredients(str(r.get("peifang") or "")):
                t = F.clean_token(tok)
                if not t:
                    continue
                got = F._resolve_one(t, names, alias)
                (ok.add(got) if got else bad.add(t))
            per.append((ok, bad))
        for i, (ok_i, bad_i) in enumerate(per):
            for j, (ok_j, _bad_j) in enumerate(per):
                if i == j:
                    continue
                extra = ok_j - ok_i
                if len(extra) == 1 and bad_i:
                    for t in bad_i:
                        x = next(iter(extra))
                        votes[t][x] += 1
                        if fname not in where[(t, x)]:
                            where[(t, x)].append(fname)
    out = []
    for t, cnt in sorted(votes.items(), key=lambda kv: -sum(kv[1].values())):
        top, n = cnt.most_common(1)[0]
        tot = sum(cnt.values())
        out.append({"alias": t, "canonical": top, "votes": n, "n_versions_pairs": tot,
                    "confidence": round(n / tot, 2),
                    "examples": where[(t, top)][:5]})
    (STAGE + r"\data\alias_candidates_from_versions.json")
    with open(STAGE + r"\data\alias_candidates_from_versions.json", "w",
              encoding="utf-8") as fh:
        json.dump({"n_formulas_multi_version": n_multi, "n_candidates": len(out),
                   "note": "只产出候选；高置信=同一异名在多个方名里都指向同一个正名",
                   "candidates": out}, fh, ensure_ascii=False, indent=1)
    print("多版本方名 %d 个 ｜ 挖出候选 %d 条" % (n_multi, len(out)))
    print("前 20 条（按票数）：")
    for x in out[:20]:
        print("   %-8s → %-8s 票 %2d/%2d（%.0f%%） 例：%s"
              % (x["alias"], x["canonical"], x["votes"], x["n_versions_pairs"],
                 100 * x["confidence"], "、".join(x["examples"][:2])))
    print()
    print("  ★ 只是**候选**：没有自动替换任何东西；要用请人工过一遍再决定")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
