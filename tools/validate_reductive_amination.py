# -*- coding: utf-8 -*-
"""专用验证：reduction_reductive_amination_001。"""
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

RID = "reduction_reductive_amination_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXT = "uspto50k_test_US04599198"


def key(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToInchiKey(m)[:14] if m else ""


def ftext(f):
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*)", str(f or "")):
        out[e] += int(n or 1)
    return out


def fc(s):
    m = Chem.MolFromSmiles(s)
    return ftext(rdMolDescriptors.CalcMolFormula(m)) if m else ftext(s)


def balance(left, target):
    l = Counter()
    for s in left:
        l += fc(s)
    l["H"] += 2
    l["O"] += 1
    l["H"] += 1
    r = fc(target)
    for k, v in ftext("H2O").items():
        r[k] += v * 2
    return all(abs(l.get(k, 0) - r.get(k, 0)) < 1e-6 for k in set(l) | set(r))


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=[RID],
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("还原")
    fails = 0
    print(eng.curated_note)

    def run(reactants, target):
        prods = eng.step([Compound(smiles=s, name="x", herb="test")
                          for s in reactants], cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit, balance(reactants, target)

    for label, reactants, target in (
            ("STD", ["O=Cc1ccccc1", "CC(C)[NH3+]"], "CC(C)NCc1ccccc1"),
            ("STDrev", ["CC(C)[NH3+]", "O=Cc1ccccc1"], "CC(C)NCc1ccccc1"),
            ("EXT", BY[EXT]["reactants"], BY[EXT]["product"]),
            ("EXTrev", list(reversed(BY[EXT]["reactants"])), BY[EXT]["product"])):
        prods, hit, bal = run(reactants, target)
        ok = bool(hit) and bal
        print("%-4s %-7s products=%d hit=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit), bal))
        fails += 0 if ok else 1

    prods, _h, _b = run(["O=Cc1ccccc1", "CCO"], "CC(C)NCc1ccccc1")
    ok = not prods
    print("%-4s NEG no amine products=%d" % ("PASS" if ok else "FAIL", len(prods)))
    fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
