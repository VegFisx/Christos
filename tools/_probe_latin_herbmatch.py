# -*- coding: utf-8 -*-
"""一次性探针：药典拉丁药材名到底命中了 HERB 里哪些行（查 over-match）。"""
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import re

Q = "Radix et Rhizoma Glycyrrhizae"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


q = _norm(Q)
c = sqlite3.connect("file:D:/TCMAI/tcm.db?mode=ro", uri=True)
hits = []
for hid, cn, la, en, al in c.execute(
        "SELECT herb_id,name_cn,COALESCE(latin,''),COALESCE(name_en,''),"
        "COALESCE(alias,'') FROM herbs"):
    if q in _norm(la) or q in _norm(en) or q in _norm(al):
        hits.append((hid, cn, la[:60], en[:60]))
print("查询 =", Q, "→ 命中", len(hits), "行")
for h in hits:
    print("   ", h)

# 各行各有多少成分（去重 SMILES）
for hid, cn, _la, _en in hits:
    n = c.execute(
        "SELECT COUNT(DISTINCT c.smiles) FROM herb_compound hc "
        "JOIN compounds c ON hc.ingredient_id=c.ingredient_id "
        "WHERE hc.herb_id=? AND c.smiles IS NOT NULL AND LENGTH(c.smiles)>3",
        (hid,)).fetchone()[0]
    print(f"    {hid} {cn}: {n} 个成分")
c.close()
