# -*- coding: utf-8 -*-
import sqlite3, sys
from collections import Counter
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

DB = "D:/TCMAI/tcm.db"
IDS = ["HERB002876", "HERB002983", "HERB007221", "HERB000162", "HERB000257", "HERB001779", "HERB000775"]
con = sqlite3.connect(DB); cur = con.cursor()
q = ",".join("?" * len(IDS))
rows = cur.execute("SELECT DISTINCT c.ingredient_id, c.smiles, hc.match_level FROM compounds c "
                   "JOIN herb_compound hc ON hc.ingredient_id = c.ingredient_id "
                   "WHERE hc.herb_id IN (%s) AND c.smiles IS NOT NULL AND c.smiles <> ''" % q, IDS).fetchall()
con.close()
seen = {}
lv = Counter()
for iid, smi, ml in rows:
    lv[ml] += 1
    if iid in seen:
        continue
    m = Chem.MolFromSmiles(smi)
    seen[iid] = m.GetNumHeavyAtoms() if m else -1
n = len(seen)
big = sum(1 for v in seen.values() if v > 25)
mid = sum(1 for v in seen.values() if 15 < v <= 25)
unp = sum(1 for v in seen.values() if v <= 0)
print("7 味药去重后有 SMILES 的成分：%d" % n)
print("  重原子 > 25（xTB 实测不可用的尺寸）：%d 个 = %.1f%%" % (big, 100.0 * big / n))
print("  重原子 16~25：%d 个" % mid)
print("  RDKit 解析失败：%d 个" % unp)
print("  若两两配对：%d 对（引擎 max_pairs 上限 4000）" % (n * (n - 1) // 2))
print("  单底物模板：%d 次套用" % n)
print("  match_level 分布（药-成分关系）：%s" % dict(lv))
