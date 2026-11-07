# -*- coding: utf-8 -*-
"""一次性探针（只读）：「哪些成分更重要」到底有没有数据依据。

查四件事：
  Q1 COCONUT 的 np_likeness 填充率（拿它排序是否可行）
  Q2 tcm.db compounds 表有哪些列（有没有含量 / 重要性类字段）
  Q3 HERB 侧 match_level 的取值分布（marker 是不是真信号）
  Q4 药典链 chp_priority 覆盖多少（Tier-0 含量测定成分）
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "sources"))
sys.path.insert(0, str(STAGE / "core"))

import sqlite3  # noqa: E402

COC = r"D:\TCMAI\coconut.db"
TCM = r"D:\TCMAI\tcm.db"


def ro(p):
    return sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)


def main() -> None:
    c = ro(COC)
    tot = c.execute("SELECT COUNT(*) FROM compounds").fetchone()[0]
    nn = c.execute("SELECT COUNT(*) FROM compounds WHERE np_likeness IS NOT NULL "
                   "AND np_likeness != ''").fetchone()[0]
    print("[Q1] COCONUT compounds = %d，np_likeness 非空 = %d（%.1f%%）"
          % (tot, nn, 100.0 * nn / max(1, tot)))
    rows = c.execute(
        "SELECT c.cnp_id, c.name, c.np_likeness FROM species_compound sc "
        "JOIN compounds c ON sc.cnp_id=c.cnp_id "
        "WHERE LOWER(sc.species)='glycyrrhiza uralensis' "
        "ORDER BY CAST(c.np_likeness AS REAL) DESC LIMIT 5").fetchall()
    print("     甘草(COCONUT) 按 np_likeness 降序前 5：")
    for r in rows:
        print("       ", r[0], str(r[1])[:40], r[2])
    c.close()

    t = ro(TCM)
    print("[Q2] tcm.db compounds 列：",
          [r[1] for r in t.execute("PRAGMA table_info(compounds)").fetchall()])
    print("     herbs 里有没有含量类列：",
          [r[1] for r in t.execute("PRAGMA table_info(herbs)").fetchall()])
    print("[Q3] herb_compound.match_level 取值分布：")
    for v, n in t.execute("SELECT COALESCE(match_level,'(空)'), COUNT(*) "
                          "FROM herb_compound GROUP BY 1 ORDER BY 2 DESC LIMIT 8"):
        print("       %-14s %d" % (v, n))
    n_marker = t.execute("SELECT COUNT(DISTINCT hc.ingredient_id) FROM herb_compound hc "
                         "WHERE hc.match_level='marker'").fetchone()[0]
    n_all = t.execute("SELECT COUNT(DISTINCT ingredient_id) FROM herb_compound").fetchone()[0]
    print("     marker 成分数 = %d / 全部有归属的成分 %d（%.1f%%）"
          % (n_marker, n_all, 100.0 * n_marker / max(1, n_all)))
    n_gc = t.execute("SELECT COUNT(DISTINCT hc.ingredient_id) FROM herb_compound hc "
                     "WHERE hc.herb_id='HERB001779' AND hc.match_level='marker'").fetchone()[0]
    n_gc_all = t.execute("SELECT COUNT(DISTINCT ingredient_id) FROM herb_compound "
                         "WHERE herb_id='HERB001779'").fetchone()[0]
    print("     甘草：marker %d / 全部 %d" % (n_gc, n_gc_all))
    t.close()

    print("[Q4] 药典链 chp_priority 覆盖")
    try:
        import chp_priority as CP
        m = CP.load_map()
        print("     药材数 =", len(m))
        g = m.get("甘草") or {}
        print("     甘草 Tier-0 条数 =", len(g))
        items = list(g.items())[:4]
        for k, v in items:
            print("       ", k, v)
    except Exception as ex:                            # noqa: BLE001
        print("     [warn] 读取失败：%s: %s" % (type(ex).__name__, ex))


if __name__ == "__main__":
    main()
