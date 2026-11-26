# -*- coding: utf-8 -*-
"""专用验证：叔溴氢解 / 叔醇脱氧两条规则。"""
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

RIDS = ["reduction_dehalogenation_cbr_001", "reduction_deoxygenation_tertiary_001"]
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}


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


def balance(smi, target, byprod):
    l = fc(smi) | {"H": 0}
    l = fc(smi).copy()
    l["H"] += 2  # co-reagent H2
    r = fc(target)
    for f in byprod:
        r += ftext(f)
    return all(abs(l.get(k, 0) - r.get(k, 0)) < 1e-6 for k in set(l) | set(r))


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=RIDS,
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("还原")
    fails = 0
    print(eng.curated_note)

    def run(smi, target, byprod):
        prods = eng.step([Compound(smiles=smi, name="x", herb="test")],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit, balance(smi, target, byprod)

    for label, smi, target, byp in (
            ("HAL std", "CC(C)(C)Br", "CC(C)C", ["HBr"]),
            ("DEOX std", "CC(C)(C)O", "CC(C)C", ["H2O"])):
        prods, hit, bal = run(smi, target, byp)
        ok = bool(hit) and bal
        print("%-4s %-10s products=%d hit=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit), bal))
        fails += 0 if ok else 1

    for label, cid, byp in (
            ("HAL ext", "uspto50k_test_US04555507", ["HBr"]),
            ("DEOX ext", "uspto50k_test_US07473703B2", ["H2O"])):
        c = BY[cid]
        prods, hit, bal = run(c["reactants"][0], c["product"], byp)
        ok = bool(hit) and bal
        print("%-4s %-10s products=%d hit=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit), bal))
        fails += 0 if ok else 1

    for label, smi in (("primary Br", "CCBr"), ("primary OH", "CCO")):
        prods, _hit, _bal = run(smi, "CC(C)C", ["H2O"])
        ok = not prods
        print("%-4s NEG %-12s products=%d" % ("PASS" if ok else "FAIL", label, len(prods)))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
