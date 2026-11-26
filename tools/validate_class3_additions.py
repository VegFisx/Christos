# -*- coding: utf-8 -*-
"""专用验证：酮炔基化 + Barbier 型加成（class 3）。"""
from __future__ import annotations

import json
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

import templates as T
from engine import Compound
from smartreact_engine import SmartReactEngine

RIDS = ["addition_ethynylation_ketone_001", "addition_barbier_aldehyde_001"]
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}


def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=RIDS,
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("室温浸泡")
    fails = 0
    print(eng.curated_note)

    def run(reactants, target):
        prods = eng.step([Compound(smiles=s, name="x", herb="test")
                          for s in reactants], cond, round_no=1, exclude_smiles=set())
        want = key(target)
        return prods, [p for p in prods if key(getattr(p, "smiles", "")) == want]

    for label, reactants, target in (
            ("ETH std", ["CC(=O)C", "C#C"], "CC(C)(O)C#C"),
            ("ETH stdrev", ["C#C", "CC(=O)C"], "CC(C)(O)C#C"),
            ("ETH ext", BY["uspto50k_test_US03932496"]["reactants"],
             BY["uspto50k_test_US03932496"]["product"]),
            ("BAR std", ["ClCc1ccccc1", "O=Cc1ccccc1"],
             "OC(Cc1ccccc1)c1ccccc1"),
            ("BAR stdrev", ["O=Cc1ccccc1", "ClCc1ccccc1"],
             "OC(Cc1ccccc1)c1ccccc1"),
            ("BAR ext", BY["uspto50k_test_US20020161150A1"]["reactants"],
             BY["uspto50k_test_US20020161150A1"]["product"])):
        prods, hit = run(reactants, target)
        ok = bool(hit)
        print("%-4s %-10s products=%d hit=%d"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit)))
        fails += 0 if ok else 1

    for label, reactants in (
            ("ETH no alkyne", ["CC(=O)C", "CCO"]),
            ("BAR no Cl", ["CCO", "O=Cc1ccccc1"])):
        prods, _hit = run(reactants, "CC(C)(O)C#C")
        ok = not prods
        print("%-4s NEG %-12s products=%d" % ("PASS" if ok else "FAIL", label, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
