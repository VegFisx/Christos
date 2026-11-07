# -*- coding: utf-8 -*-
"""Audit the formula input path the same way the herb path was audited.

Measures: how many formulas exist, how many share a name, how often the
composition field parses into herb names, and how often those names resolve
against the herb table.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\github-release\christos")
for _p in ("sources", "core", "libs"):
    d = STAGE / _p
    if d.is_dir() and str(d) not in sys.path:
        sys.path.insert(0, str(d))

import herb as H  # noqa: E402

FORMULA_JSON = Path(r"D:\TCMAI\data\formula_db.json")
SPLIT = re.compile(r"[，,、;；。\s]+")
PAREN = re.compile(r"[（(][^）)]*[）)]")
# 括号未闭合时的兜底：从最后一个左括号一直吃到串尾
PAREN_OPEN = re.compile(r"[（(][^）)]*$")
# 纯右括号残片（括号内逗号被先切开时产生）
PAREN_TAIL = re.compile(r"^[^（(]*[）)]")


def clean_token(tok: str) -> str:
    t = tok or ""
    t = PAREN.sub("", t)
    t = PAREN_OPEN.sub("", t)
    t = t.strip("（）()").strip()
    t = re.sub(r"\d+(\.\d+)?\s*(两|钱|分|克|g|枚|片|个|升|毫升|ml)", "", t)
    # 中文数字剂量只在词尾出现时剥离，避免误伤「三七」这类药名
    t = re.sub(r"[一二三四五六七八九十百半]+\s*(两|钱|分|克|枚|片|个|升|毫升)$", "", t)
    t = re.sub(r"各等分|等分|减半|适量", "", t)
    return t.strip()


def main() -> int:
    data = json.loads(FORMULA_JSON.read_text(encoding="utf-8"))
    rows = []
    for v in data.values():
        if isinstance(v, list):
            rows.extend(v)
    print("方剂记录 %d 条" % len(rows))

    names = Counter(r.get("name") for r in rows if r.get("name"))
    multi = {k: n for k, n in names.items() if n > 1}
    print("唯一方名 %d 个；同名多版本 %d 个（涉及 %d 条记录）"
          % (len(names), len(multi), sum(multi.values())))
    top = sorted(multi.items(), key=lambda x: -x[1])[:5]
    for k, n in top:
        print("   %-16s %d 个版本" % (k, n))

    cur = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True).cursor()
    total_tok = resolved = 0
    failed = Counter()
    with_comp = 0
    for r in rows:
        comp = (r.get("peifang") or "").strip()
        if not comp:
            continue
        with_comp += 1
        # 先剥掉整段括号内容，再按分隔符切开 —— 括号内常有逗号，
        # 先切会把 "黄连（去须，微炒）" 拆成残片。
        stripped = PAREN.sub("", comp)
        stripped = PAREN_OPEN.sub("", stripped)
        toks = [clean_token(t) for t in SPLIT.split(stripped)]
        toks = [t for t in toks if t and len(t) <= 12]
        for t in toks:
            total_tok += 1
            if H._resolve_herb_ids(cur, t):
                resolved += 1
            else:
                failed[t] += 1

    print("\n有组成字段的方剂 %d 条" % with_comp)
    print("药材 token 合计 %d，解析成功 %d（%.1f%%）"
          % (total_tok, resolved, 100.0 * resolved / max(1, total_tok)))
    print("未解析 token %d 种，最常见：" % len(failed))
    for t, n in failed.most_common(10):
        print("   %-14s %d 次" % (t, n))

    out = STAGE / "reports" / "paper" / "formula_input_audit_20261025.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "formulas": len(rows), "unique_names": len(names),
        "multi_version_names": len(multi),
        "with_composition": with_comp,
        "tokens": total_tok, "resolved": resolved,
        "top_failed": failed.most_common(20),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n结果 -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
