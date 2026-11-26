# -*- coding: utf-8 -*-
"""专用验证：addition_hcl_alkene_001。"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
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
from rdkit.Chem import rdMolDescriptors

import templates as T
from engine import Compound
from smartreact_engine import SmartReactEngine

RID = "addition_hcl_alkene_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = "uspto50k_test_US07223769B2"


def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def fcount(f):
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", str(f or "")):
        out[e] += int(n or 1)
    return out


def fc(s):
    m = Chem.MolFromSmiles(s)
    return fcount(rdMolDescriptors.CalcMolFormula(m)) if m else fcount(s)


def balance(left, target):
    l = Counter()
    for s in left:
        l += fc(s)
    return l == fc(target)


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=[RID],
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("室温浸泡")
    fails = 0
    print(eng.curated_note)

    def run(reactants, target):
        prods = eng.step([Compound(smiles=s, name="x", herb="test") for s in reactants],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit, balance(reactants, target)

    prods, hit, bal = run(["CC=C", "Cl"], "CC(Cl)C")
    ok = bool(hit) and bal
    print("%-4s STD products=%d hit=%d balance=%s"
          % ("PASS" if ok else "FAIL", len(prods), len(hit), bal))
    fails += 0 if ok else 1

    c = BY[EXTERNAL]
    prods, hit, bal = run(c["reactants"], c["product"])
    ok = bool(hit) and bal
    print("%-4s EXT %s products=%d hit=%d balance=%s"
          % ("PASS" if ok else "FAIL", EXTERNAL, len(prods), len(hit), bal))
    fails += 0 if ok else 1

    prods, _hit, _bal = run(["CC=C", "CCO"], "CC(Cl)C")
    ok = not prods
    print("%-4s NEG no Cl products=%d" % ("PASS" if ok else "FAIL", len(prods)))
    fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
