# -*- coding: utf-8 -*-
"""一次性探针（只读）：拉丁名到底是「种名」还是「药材名」，两库各能匹配多少。

回答三个问题：
  1) COCONUT 的 species 字段长什么样、能否按种名命中；
  2) HERB 的 latin / name_en 列里，两种写法各占多少；
  3) 甘草/银杏/白鲜皮 这几个已知药材在两库里的落点。
"""
from __future__ import annotations

import re
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TCM = r"D:\TCMAI\tcm.db"
COC = r"D:\TCMAI\coconut.db"


def ro(path: str) -> sqlite3.Connection:
    return sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)


PART = (r"\b(Radix|Rhizoma|Folium|Herba|Cortex|Fructus|Semen|Flos|Ramulus|Caulis|"
        r"Lignum|Resina|Pericarpium|Bulbus|Nodus|Spica|Stigma|Aris|Medulla|Exocarpium)\b")


def main() -> None:
    print("[1] COCONUT species 样例")
    c = ro(COC)
    rows = c.execute("SELECT DISTINCT species FROM species_compound LIMIT 6").fetchall()
    for (s,) in rows:
        print("    ", s)
    n = c.execute("SELECT COUNT(DISTINCT species) FROM species_compound").fetchone()[0]
    print("     distinct species =", n)
    for kw in ("Glycyrrhiza uralensis", "Ginkgo biloba", "Dictamnus dasycarpus",
               "Glycirrhiza uralensis"):
        k = kw.lower().replace(" ", "%")
        n_species = c.execute(
            "SELECT COUNT(DISTINCT species) FROM species_compound WHERE LOWER(species) LIKE ?",
            ("%" + k + "%",)).fetchone()[0]
        n_cmp = c.execute(
            "SELECT COUNT(DISTINCT cnp_id) FROM species_compound WHERE LOWER(species) LIKE ?",
            ("%" + k + "%",)).fetchone()[0]
        print(f"     '{kw}': species 命中 {n_species} 个 / 化合物 {n_cmp} 个")
    # 拼错时 COCONUT 里有没有近似种名
    for hit in c.execute(
            "SELECT DISTINCT species FROM species_compound "
            "WHERE LOWER(species) LIKE 'gly%ur%' LIMIT 12").fetchall():
        print("     [近似族] ", hit[0])
    c.close()

    print("[2] HERB herbs 列与形态统计")
    t = ro(TCM)
    cols = [r[1] for r in t.execute("PRAGMA table_info(herbs)").fetchall()]
    print("     columns =", cols)
    tot = t.execute("SELECT COUNT(*) FROM herbs").fetchone()[0]
    print("     总行数 =", tot)
    for col in ("latin", "name_en", "alias", "pinyin"):
        if col not in cols:
            continue
        empty = pharm = spec = 0
        for (v,) in t.execute(f"SELECT COALESCE({col},'') FROM herbs").fetchall():
            v = (v or "").strip()
            if not v:
                empty += 1
            elif re.search(PART, v, re.I):
                pharm += 1
            elif re.match(r"^[A-Z][a-z]{2,} [a-z][a-z\-]{2,}", v):
                spec += 1
        other = tot - empty - pharm - spec
        print(f"     {col}: 空 {empty} | 含部位词(药材名式) {pharm} | "
              f"像双名法(种名式) {spec} | 其他 {other}")
    print("[3] 甘草相关行（HERB）")
    for r in t.execute(
            "SELECT herb_id,name_cn,latin,name_en FROM herbs "
            "WHERE name_cn LIKE '%甘草%' OR name_en LIKE '%Glycyrrhiz%' "
            "   OR latin LIKE '%Glycyrrhiz%' LIMIT 12").fetchall():
        print("    ", r)
    print("[4] 银杏 / 白鲜 相关行（HERB）")
    for r in t.execute(
            "SELECT herb_id,name_cn,latin,name_en FROM herbs "
            "WHERE name_cn LIKE '%银杏%' OR name_cn LIKE '%白鲜%' "
            "   OR name_en LIKE '%Ginkgo%' OR latin LIKE '%Ginkgo%' "
            "   OR name_en LIKE '%Dictamnus%' OR latin LIKE '%Dictamnus%' LIMIT 12").fetchall():
        print("    ", r)
    t.close()


if __name__ == "__main__":
    main()
