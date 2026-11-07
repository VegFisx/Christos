# -*- coding: utf-8 -*-
r"""探针：SMARTS 查询原子上的氢数到底该怎么读？（delta_h 恒为 0 的原因）"""
from __future__ import annotations

import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import RDLogger
from rdkit.Chem import rdChemReactions

RDLogger.DisableLog("rdApp.*")

CASES = [
    "[C:1]-[CH;D2;+0:2]=[O;H0;D1;+0:3]>>[C:1]-[CH2;D2;+0:2]-[OH;D1;+0:3]",   # 醛->醇, 期望 +2
    "[OH;D1;+0:1]-[CH2;D2;+0:2]-[c:3]>>[O;H0;D1;+0:1]=[CH;D2;+0:2]-[c:3]",   # 醇->醛, 期望 -2
    "[NH2;D1;+0:1]-[CH2;D2;+0:2]-[c:3]>>[N;H0;D1;+0:1]#[C;H0;D2;+0:2]-[c:3]",  # 胺->腈, 期望 -4
]
print("=" * 100)
print("SMARTS 查询原子的氢计数：几种读法对比")
print("=" * 100)
for sm in CASES:
    rx = rdChemReactions.ReactionFromSmarts(sm)
    print(f"\n{sm[:80]}")
    for side, patts in (("R", rx.GetReactants()), ("P", rx.GetProducts())):
        for patt in patts:
            for a in patt.GetAtoms():
                if a.GetAtomicNum() <= 1:
                    continue
                print(f"   {side} {a.GetSymbol():<2} map={a.GetAtomMapNum():<3} "
                      f"GetNumExplicitHs={a.GetNumExplicitHs():<2} "
                      f"GetExplicitValence={a.GetExplicitValence():<2} "
                      f"GetDegree={a.GetDegree():<2} "
                      f"| GetSmarts={a.GetSmarts()}")
    # 备选：化学式法（把查询当分子 AddHs 后数 H）
    def h_via_mol(patts):
        tot = 0
        for p in patts:
            m = rdChemReactions.ChemicalReaction()  # noqa: F841  (占位，下面用另一种方式)
        return tot
