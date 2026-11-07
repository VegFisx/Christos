# -*- coding: utf-8 -*-
"""一次性探针（只读）：COCONUT 适配还缺什么。

回答三问：
  Q1 只给「属名」（如 glycyrrhiza）时，能不能列出一族物种？各有多少成分？
  Q2 HERB ↔ COCONUT 的成分共享率，按**规范 SMILES** 算到底多高？（之前只比过字符串）
  Q3 compounds 的 chemical_class / super_class 能不能用来组织植物化学成分？
"""
from __future__ import annotations

import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TCM = r"D:\TCMAI\tcm.db"
COC = r"D:\TCMAI\coconut.db"


def ro(p):
    return sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)


def canon(s):
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m is not None else None


def main() -> None:
    c = ro(COC)
    print("[Q1] 只给属名的情况")
    for g in ("glycyrrhiza", "ginkgo", "panax"):
        rows = c.execute(
            "SELECT species, COUNT(DISTINCT cnp_id) n FROM species_compound "
            "WHERE LOWER(species) LIKE ? GROUP BY species ORDER BY n DESC",
            (g + " %",)).fetchall()
        tot = sum(r[1] for r in rows)
        print(f"     {g}: {len(rows)} 个物种，共 {tot} 条物种-成分记录")
        for sp, n in rows[:5]:
            print(f"        {sp:<38} {n}")

    print("[Q2] HERB vs COCONUT 共享（规范 SMILES 口径）")
    t = ro(TCM)
    for cn, hid, sp in (("甘草", "HERB001779", "glycyrrhiza uralensis"),
                        ("白鲜皮", "HERB000286", "dictamnus dasycarpus"),
                        ("银杏叶", "HERB006632", "ginkgo biloba")):
        h = {canon(r[0]) for r in t.execute(
            "SELECT c.smiles FROM herb_compound hc JOIN compounds c "
            "ON hc.ingredient_id=c.ingredient_id WHERE hc.herb_id=? "
            "AND c.smiles IS NOT NULL AND LENGTH(c.smiles)>3", (hid,)).fetchall()} - {None}
        k = {canon(r[0]) for r in c.execute(
            "SELECT c.smiles FROM species_compound sc JOIN compounds c "
            "ON sc.cnp_id=c.cnp_id WHERE LOWER(sc.species)=? "
            "AND c.smiles IS NOT NULL AND LENGTH(c.smiles)>3", (sp,)).fetchall()} - {None}
        inter = len(h & k)
        print(f"     {cn}: HERB 规范 {len(h)} | COCONUT 规范 {len(k)} | 共享 {inter}"
              f"（占 HERB {100.0*inter/max(1,len(h)):.1f}%）| 并集 {len(h|k)}")
    t.close()

    print("[Q3] chemical_class 取值样例（COCONUT）")
    for col in ("chemical_super_class", "chemical_class"):
        rows = c.execute(
            f"SELECT {col}, COUNT(*) n FROM compounds WHERE {col} IS NOT NULL "
            f"AND {col} != '' GROUP BY {col} ORDER BY n DESC LIMIT 8").fetchall()
        empty = c.execute(
            f"SELECT COUNT(*) FROM compounds WHERE {col} IS NULL OR {col}=''").fetchone()[0]
        print(f"     {col}: 空 {empty}/272992")
        for v, n in rows:
            print(f"        {str(v)[:44]:<46} {n}")

    print("     甘草(COCONUT) 的成分分布：")
    for v, n in c.execute(
            "SELECT COALESCE(NULLIF(c.chemical_class,''),'(未分类)') k, "
            "COUNT(DISTINCT c.cnp_id) "
            "FROM species_compound sc JOIN compounds c ON sc.cnp_id=c.cnp_id "
            "WHERE LOWER(sc.species)='glycyrrhiza uralensis' GROUP BY k "
            "ORDER BY 2 DESC LIMIT 10"):
        print(f"        {str(v)[:44]:<46} {n}")
    c.close()


if __name__ == "__main__":
    main()
