# -*- coding: utf-8 -*-
"""验证 curated 三反应物模板枚举（Mannich 标准例，不写入 rules.json）。"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
from rdkit.Chem import rdChemReactions

from engine import Compound
from smartreact_engine import SmartReactEngine

SMARTS = (
    "[C;D1;H3:1]-[NH;D2;+0:2]-[CH3;D1;+0:3]."
    "[CH2;D1;+0:4]=[O;D1;H0:5]."
    "[CH3;D1;+0:6]-[C;H0;D3;+0:7](-[CH3;D1;+0:8])=[O;H0;D1;+0:9]>>"
    "[C;D1;H3:1]-[N;H0;D3;+0:2](-[CH3;D1;+0:8])-[CH2;D2;+0:3]-"
    "[CH2;D2;+0:7]-[C;H0;D3;+0:4](-[CH3;D1;+0:6])=[O;D1;H0:5].[OH2;D0;+0:9]"
)
TARGET = "CC(=O)CCN(C)C"


def main():
    eng = SmartReactEngine(
        use_curated_templates=False, use_extra_templates=False,
        use_mono_templates=False, use_base_templates=False,
        rescue=False, gate_conditions=False, stereo_enum_cap=0,
        max_triples=10,
    )
    rx = rdChemReactions.ReactionFromSmarts(SMARTS)
    eng.curated_triple_templates = [(SMARTS, rx, "mannich_test")]
    seeds = [Compound(smiles=s, name="r%d" % i, herb="test")
             for i, s in enumerate(("CNC", "C=O", "CC(=O)C"))]
    subs = [(c, Chem.MolToSmiles(Chem.MolFromSmiles(c.smiles))) for c in seeds]
    chunk = [(0, 1), (0, 2), (1, 2)]
    res = eng._extra_results(chunk, subs, None)
    prods = set()
    for r in res:
        if r.reaction_name == "mannich_test":
            prods.update(r.products)
    want = Chem.MolToSmiles(Chem.MolFromSmiles(TARGET))
    ok = want in prods
    print("triple results", len(res), "products", sorted(prods)[:5])
    print("PASS" if ok else "FAIL", "target", want)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
