# -*- coding: utf-8 -*-
"""规则广度审计：单底物规则在 200 个真实 tcm.db 化合物上的触发率。

用途：找「几乎什么都反应」的过宽规则，以及「在通用底物上从不触发」的过窄规则。
双底物规则不在本面板统计（需要配对底物）。
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for p in (ROOT / "libs", ROOT / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402

RDLogger.DisableLog("rdApp.*")

DB = "file:D:/TCMAI/tcm.db?mode=ro"
RULES = ROOT / "rules" / "rules.json"
N_PANEL = 200

con = sqlite3.connect(DB, uri=True)
cur = con.cursor()
rows = cur.execute(
    "SELECT ingredient_id, name_en, COALESCE(isomeric_smiles, smiles, '') "
    "FROM compounds WHERE smiles IS NOT NULL AND TRIM(smiles) != '' "
    "ORDER BY ingredient_id").fetchall()
con.close()

panel = []
step = max(1, len(rows) // (N_PANEL * 8))
for i in range(0, len(rows), step):
    iid, name, smi = rows[i]
    m = Chem.MolFromSmiles(smi)
    if m is None or not (4 <= m.GetNumHeavyAtoms() <= 60):
        continue
    panel.append((iid, name, Chem.MolToSmiles(m)))
    if len(panel) >= N_PANEL:
        break
print("面板 %d 个化合物（从 %d 行中抽样）" % (len(panel), len(rows)))

rules = json.load(open(RULES, encoding="utf-8"))["rules"]
out = []
for r in rules:
    if r.get("status") != "active":
        continue
    sm = r.get("smarts") or ""
    try:
        rx = rdChemReactions.ReactionFromSmarts(sm)
    except Exception:
        continue
    if rx is None or rx.GetNumReactantTemplates() != 1:
        out.append((r["id"], "pair/non-mono", 0, 0))
        continue
    fired = 0
    nprod = 0
    for _iid, _name, smi in panel:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        try:
            res = rx.RunReactants((m,))
        except Exception:
            continue
        if res:
            fired += 1
            nprod += len(res)
    out.append((r["id"], "mono", fired, nprod))

mono = [(rid, f, n) for rid, kind, f, n in out if kind == "mono"]
mono.sort(key=lambda x: -x[1])
print("\n单底物规则 %d 条；触发率（200 个真实化合物）：" % len(mono))
for rid, f, n in mono:
    print("  %-40s %3d/%d = %5.1f%%  例/命中=%.2f"
          % (rid, f, len(panel), 100.0 * f / max(1, len(panel)),
             n / max(1, f)))
print("\n双底物/非单底物规则 %d 条（未统计）：" % (len(out) - len(mono)))
print("  " + ", ".join(rid for rid, kind, _f, _n in out if kind != "mono"))
