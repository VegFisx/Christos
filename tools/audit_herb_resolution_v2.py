# -*- coding: utf-8 -*-
"""Extended herb-resolution audit.

The Latin group is drawn from the herb table itself rather than hand-written,
so the test measures whether a real binomial resolves back to its own herb.

Read-only.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "sources", STAGE / "core", STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import herb as H  # noqa: E402

EXACT = ["甘草", "当归", "茯苓", "白术", "川芎", "黄芪", "人参", "生地黄",
         "大黄", "桂枝", "陈皮", "半夏", "白芍", "丹参", "黄连", "柴胡",
         "防风", "桔梗", "连翘", "金银花"]

ALIAS = ["黄耆", "龙胆草", "国老", "川军", "云苓", "枣皮", "怀山药",
         "淮山", "元参", "寸冬"]

PROCESSED = ["炙甘草", "炒白术", "姜半夏", "熟地黄", "酒大黄",
             "醋柴胡", "盐杜仲", "麸炒枳壳", "蜜炙黄芪", "清半夏"]

NEGATIVE = ["阿巴阿巴", "zzzz", "测试药名", "甘", "不存在的中药",
            "qqqq", "12345", "随便写写", "notaherb", "某某草"]


def main() -> int:
    conn = H._connect(H.DEFAULT_DB)
    cur = conn.cursor()

    rows = []

    def run(name, group, expect=None):
        hits = H._resolve_herb_ids(cur, name)
        names = [h[1] for h in hits]
        rec = {
            "input": name,
            "group": group,
            "n_candidates": len(hits),
            "stages": sorted({h[2] for h in hits}),
            "candidates": names[:6],
        }
        if expect:
            rec["expected"] = expect
            rec["correct"] = expect in names
        rows.append(rec)

    for n in EXACT:
        run(n, "exact", expect=n)
    for n in ALIAS:
        run(n, "alias")
    for n in PROCESSED:
        run(n, "processed")
    for n in NEGATIVE:
        run(n, "negative")

    # Latin group straight from the table.
    cur.execute(
        "SELECT name_cn, latin FROM herbs "
        "WHERE latin IS NOT NULL AND TRIM(latin) <> '' "
        "ORDER BY herb_id LIMIT 25"
    )
    latin_rows = cur.fetchall()
    for name_cn, latin in latin_rows:
        run(latin, "latin", expect=name_cn)

    conn.close()

    summary = {}
    for group in ("exact", "alias", "processed", "negative", "latin"):
        sub = [r for r in rows if r["group"] == group]
        n = len(sub)
        resolved = sum(1 for r in sub if r["n_candidates"] > 0)
        ambiguous = sum(1 for r in sub if r["n_candidates"] > 1)
        correct = sum(1 for r in sub if r.get("correct"))
        with_expect = sum(1 for r in sub if "expected" in r)
        summary[group] = {
            "n": n,
            "resolved": resolved,
            "unresolved": n - resolved,
            "ambiguous": ambiguous,
            "correct": correct,
            "with_expectation": with_expect,
        }

    out = STAGE / "reports" / "paper" / "herb_resolution_audit_v2_20261022.json"
    out.write_text(
        json.dumps({"cases": rows, "summary": summary},
                   ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print("%-10s %4s %9s %11s %9s %8s" %
          ("group", "n", "resolved", "unresolved", "ambiguous", "correct"))
    for g, s in summary.items():
        print("%-10s %4d %9d %11d %9d %8s"
              % (g, s["n"], s["resolved"], s["unresolved"],
                 s["ambiguous"],
                 ("%d/%d" % (s["correct"], s["with_expectation"])
                  if s["with_expectation"] else "-")))
    print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
