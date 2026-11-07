# -*- coding: utf-8 -*-
"""一次性探针（只读）第二轮：HERB 里有多少行带「种名式拉丁」；同一味药两库成分数对照。"""
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

PART = (r"(Radix|Rhizoma|Folium|Herba|Cortex|Fructus|Semen|Flos|Ramulus|Caulis|"
        r"Lignum|Resina|Pericarpium|Bulbus|Nodus|Spica|Stigma|Medulla)")
BINOM = re.compile(r"^[A-Za-z]{3,}\s+[A-Za-z]{3,}")


def ro(p):
    return sqlite3.connect("file:" + p.replace("\\", "/") + "?mode=ro", uri=True)


def main() -> None:
    t, c = ro(TCM), ro(COC)

    # A. HERB 两列里「种名式」到底多少行（大小写不敏感，先排掉部位词）
    for col in ("latin", "name_en"):
        spec = []
        for hid, cn, v in t.execute(
                f"SELECT herb_id,name_cn,COALESCE({col},'') FROM herbs").fetchall():
            v = (v or "").strip()
            if not v or re.search(PART, v, re.I):
                continue
            for piece in re.split(r"[;,]", v):
                piece = piece.strip()
                if BINOM.match(piece):
                    spec.append((hid, cn, piece))
                    break
        print(f"[A] HERB.{col} 种名式行数 = {len(spec)}")
        for r in spec[:5]:
            print("     ", r)

    # B. 逐味药对照：HERB（按中文名）vs COCONUT（按种名）
    cases = [("甘草", "HERB001779", "Glycyrrhiza uralensis"),
             ("白鲜皮", "HERB000286", "Dictamnus dasycarpus"),
             ("银杏叶", "HERB006632", "Ginkgo biloba")]
    print("[B] HERB vs COCONUT 成分数（去重 SMILES 口径）")
    for cn, hid, sp in cases:
        hset = {r[0] for r in t.execute(
            "SELECT c.smiles FROM herb_compound hc "
            "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
            "WHERE hc.herb_id=? AND c.smiles IS NOT NULL AND LENGTH(c.smiles)>3",
            (hid,)).fetchall()}
        kset = {r[0] for r in c.execute(
            "SELECT c.smiles FROM species_compound sc "
            "JOIN compounds c ON sc.cnp_id=c.cnp_id "
            "WHERE LOWER(sc.species)=? AND c.smiles IS NOT NULL AND LENGTH(c.smiles)>5",
            (sp.lower(),)).fetchall()}
        print(f"     {cn}（种名 {sp}）: HERB {len(hset)} 个 | COCONUT {len(kset)} 个 "
              f"| 两库共享 {len(hset & kset)} 个 | 并集 {len(hset | kset)} 个")

    # C. 输入「种名」时，HERB 侧能反查到谁
    for sp in ("Glycyrrhiza uralensis", "Ginkgo biloba", "Dictamnus dasycarpus"):
        toks = [x.lower() for x in sp.split()]
        hits = []
        for hid, cn, la, en, al in t.execute(
                "SELECT herb_id,name_cn,COALESCE(latin,''),COALESCE(name_en,''),"
                "COALESCE(alias,'') FROM herbs").fetchall():
            blob = (la + " " + en + " " + al).lower()
            if all(tk in blob for tk in toks):
                hits.append((hid, cn))
        print(f"[C] '{sp}' 在 HERB 里反查到 {sorted(hits)}")
    t.close()
    c.close()


if __name__ == "__main__":
    main()
