# -*- coding: utf-8 -*-
r"""Formula-library coverage with a safe name normalizer (read-only).

Compared with audit_formula_db_coverage.py (strict exact match), this version
also tries, in order:

  1. cleaning (same as the strict tool),
  2. removing private-use/corrupt characters,
  3. stripping a trailing dose written in Chinese numerals ("甘草半", "各二两"),
  4. stripping a processing prefix ("炙甘草", "炒白术", "姜半夏", "生石膏"),
  5. stripping a form suffix ("黄芩片", "当归条").

A candidate is accepted only if the resulting string exists in the herb
name/alias set, so this cannot invent fuzzy matches.  It also reports a
separate "herb-like" denominator that excludes obvious excipient/chemical
names, so the strict number stays comparable.

Read-only: formula_db.csv is read; tcm.db is opened with mode=ro.
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
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\formula_db_coverage2_20261124.json")

SPLIT = re.compile(r"[，,、;；/]+")
DOSE = re.compile(r"\d+(?:\.\d+)?\s*(?:g|kg|mg|克|千克|毫克|钱|两|枚|片|个|只|条|ml|mL|毫升|%|％)?", re.I)
PAREN = re.compile(r"[（(].*?[)）]")
SUFFIX = ("（炙）", "(炙)", "（制）", "(制)", "（炒）", "(炒)", "（炭）", "(炭)",
          "（生）", "(生)", "（姜制）", "(姜制)", "（酒制）", "(酒制)")
JUNK = {"炒", "焙", "锉", "切", "研", "晒干", "微炒", "去皮", "去皮脐",
        "炙", "煨", "蒸", "煮", "炮", "洗", "浸", "酒洗", "酒蒸", "炒黄",
        "炒焦", "炒炭", "焙干", "阴干", "捣", "捣碎", "为末", "末"}

# processing prefixes, longest first (form: 炙甘草 / 炒白术 / 麸炒枳壳)
PROC = ("麸炒", "土炒", "醋炙", "酒炙", "蜜炙", "姜制", "酒制", "醋制", "盐制",
        "煅", "炙", "炒", "制", "炮", "焦", "炭", "生", "熟", "法", "清", "姜",
        "酒", "醋", "盐", "蜜")
FORM = ("片", "条", "段", "块", "个", "只", "枚", "丝")
PRIVATE = re.compile(r"[\ue000-\uf8ff]")
CN_TAIL = re.compile(r"(?:各)?(?:[一二三四五六七八九十百千半零]+|多少)?"
                     r"(?:两|钱|分|厘|毫|枚|片|个|只|条|段|块|升|合|寸|尺|斤|克|毫升)?$")
# obvious non-herb components: names ending in a chemical/excipient suffix
CHEM_TAIL = ("酸镁", "酸钠", "酸钾", "酸钙", "酸锌", "硬脂酸", "糊精", "淀粉",
             "纤维素", "甘油", "乙醇", "糖浆", "色素", "香精")


def clean(name: str) -> str:
    s = name.strip()
    s = re.sub(r"[。．.；;：:]+$", "", s)
    for x in SUFFIX:
        s = s.replace(x, "")
    s = PAREN.sub("", s)
    s = re.sub(r"[（(].*$", "", s)
    s = s.replace("）", "").replace(")", "")
    s = DOSE.sub("", s)
    s = re.sub(r"(?:分|半|两|钱|斤|克)$", "", s)
    s = re.sub(r"[【】\[\]<>《》\"'“”‘’\s]", "", s)
    return s


def variants(name: str):
    """Yield normalized candidates, most conservative first (deduplicated)."""
    s = clean(PRIVATE.sub("", name))
    out = []
    if s:
        out.append(s)
    s2 = CN_TAIL.sub("", s)
    if s2 and s2 != s:
        out.append(s2)
    for base in out[:]:
        for p in PROC:
            if base.startswith(p) and len(base) > len(p):
                out.append(base[len(p):])
        for f in FORM:
            if base.endswith(f) and len(base) > len(f):
                out.append(base[:-len(f)])
        for p in PROC:
            if not base.startswith(p):
                continue
            t = base[len(p):]
            for f in FORM:
                if t.endswith(f) and len(t) > len(f):
                    out.append(t[:-len(f)])
    seen = set()
    for x in out:
        if x and x not in seen:
            seen.add(x)
            yield x


def is_chem(name: str) -> bool:
    return any(name.endswith(x) for x in CHEM_TAIL)


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
            exact, relaxed, unresolved = [], [], []
            chem = []
            for h in herbs:
                if h in names:
                    exact.append(h)
                    relaxed.append(h)
                    continue
                got = None
                for v in variants(h):
                    if v in names:
                        got = v
                        break
                if got:
                    relaxed.append(got)
                else:
                    unresolved.append(h)
                    if is_chem(h):
                        chem.append(h)
            rows.append({
                "formula": r.get("方名") or "",
                "n_ingredients": len(herbs),
                "n_exact": len(exact),
                "n_relaxed": len(relaxed),
                "n_unresolved": len(unresolved),
                "n_chem": len(chem),
                "unresolved": unresolved,
            })

    n = len(rows)
    total = sum(x["n_ingredients"] for x in rows)
    exact = sum(x["n_exact"] for x in rows)
    relaxed = sum(x["n_relaxed"] for x in rows)
    chem = sum(x["n_chem"] for x in rows)
    herb_total = total - chem
    full_relaxed = sum(1 for x in rows if x["n_unresolved"] == 0)
    full_relaxed_no_chem = sum(1 for x in rows
                               if x["n_unresolved"] - x["n_chem"] == 0)
    unresolved = Counter(h for x in rows for h in x["unresolved"] if not is_chem(h))
    summary = {
        "formula_rows": n,
        "ingredient_mentions": total,
        "exact_resolved": exact,
        "exact_pct": round(100.0 * exact / total, 2) if total else 0,
        "relaxed_resolved": relaxed,
        "relaxed_pct": round(100.0 * relaxed / total, 2) if total else 0,
        "relaxed_pct_herb_like": round(100.0 * relaxed / herb_total, 2)
        if herb_total else 0,
        "chem_like_unresolved": chem,
        "formulas_all_relaxed_pct": round(100.0 * full_relaxed / n, 2) if n else 0,
        "formulas_all_relaxed_pct_herb_like":
            round(100.0 * full_relaxed_no_chem / n, 2) if n else 0,
        "top_unresolved_herb_like": unresolved.most_common(30),
    }
    OUT.write_text(json.dumps({"summary": summary, "rows": rows},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
