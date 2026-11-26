# -*- coding: utf-8 -*-
r"""Measure how much of the user's formula library resolves into tcm.db herbs.

Read-only: formula_db.csv is read; tcm.db is opened with mode=ro.  No writes to
D:\TCMAI.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

FORMULA = Path(r"D:\TCMAI\data\formula_db.csv")
TCM = Path(r"D:\TCMAI\tcm.db")
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\formula_db_coverage_20261124.json")

SPLIT = re.compile(r"[，,、;；/]+")
DOSE = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|mg|克|千克|毫克|钱|两|枚|片|个|只|条|ml|mL|毫升|%|％)?", re.I)
PAREN = re.compile(r"[（(].*?[)）]")
SUFFIX = ("（炙）", "(炙)", "（制）", "(制)", "（炒）", "(炒)", "（炭）", "(炭)",
          "（生）", "(生)", "（姜制）", "(姜制)", "（酒制）", "(酒制)")
# Fragments left over from processing annotations in the source text; they are
# not ingredients and should not inflate the unresolved denominator.
JUNK = {"炒", "焙", "锉", "切", "研", "晒干", "微炒", "去皮", "去皮脐",
        "炙", "煨", "蒸", "煮", "炮", "洗", "浸", "酒洗", "酒蒸", "炒黄",
        "炒焦", "炒炭", "焙干", "阴干", "捣", "捣碎", "为末", "末"}

def clean(name: str) -> str:
    s = name.strip()
    s = re.sub(r"[。．.；;：:]+$", "", s)
    for x in SUFFIX:
        s = s.replace(x, "")
    s = PAREN.sub("", s)
    # Unmatched parenthetical annotations (the source CSV sometimes splits
    # "（去须" / "微炒）" across comma-separated fragments).
    s = re.sub(r"[（(].*$", "", s)
    s = s.replace("）", "").replace(")", "")
    s = DOSE.sub("", s)
    s = re.sub(r"(?:分|半|两|钱|斤|克)$", "", s)
    s = re.sub(r"[【】\[\]<>《》\"'“”‘’\s]", "", s)
    return s

def main() -> int:
    con = sqlite3.connect(f"file:{TCM}?mode=ro", uri=True)
    names = set()
    for (n,) in con.execute("SELECT name_cn FROM herbs WHERE name_cn IS NOT NULL"):
        n = str(n).strip()
        if n:
            names.add(n)
    for (n,) in con.execute("SELECT alias FROM herbs WHERE alias IS NOT NULL"):
        for x in re.split(r"[,，、;；/|]+", str(n)):
            x = x.strip()
            if x:
                names.add(x)
    con.close()

    rows = []
    with FORMULA.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            formula = (r.get("配方") or "").strip()
            herbs = []
            for x in SPLIT.split(formula):
                x = clean(x)
                if x and x not in ("适量", "各适量", "等份", "适量。", "少许") \
                        and x not in JUNK:
                    herbs.append(x)
            if not herbs:
                continue
            resolved = [h for h in herbs if h in names]
            rows.append({
                "formula": r.get("方名") or "",
                "source": r.get("出处") or "",
                "n_ingredients": len(herbs),
                "n_resolved": len(resolved),
                "resolved": resolved,
                "unresolved": [h for h in herbs if h not in names],
            })

    n = len(rows)
    all_rows = [x for x in rows if x["n_resolved"] == x["n_ingredients"]]
    none_rows = [x for x in rows if x["n_resolved"] == 0]
    total_ing = sum(x["n_ingredients"] for x in rows)
    total_res = sum(x["n_resolved"] for x in rows)
    unresolved = Counter(h for x in rows for h in x["unresolved"])
    summary = {
        "formula_rows": n,
        "formulas_fully_resolved": len(all_rows),
        "formulas_fully_resolved_pct": round(100.0 * len(all_rows) / n, 2) if n else 0,
        "formulas_none_resolved": len(none_rows),
        "ingredient_mentions": total_ing,
        "ingredient_mentions_resolved": total_res,
        "ingredient_resolution_pct": round(100.0 * total_res / total_ing, 2) if total_ing else 0,
        "top_unresolved": unresolved.most_common(30),
        "examples_fully_resolved": all_rows[:5],
        "examples_unresolved": none_rows[:5],
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
