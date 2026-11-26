# -*- coding: utf-8 -*-
"""专用验证：cyclization_quaternary_ammonium_001（窄模板）。"""
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

RID = "cyclization_quaternary_ammonium_001"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = "uspto50k_test_US20110257395A1"


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
    l = fc(left)
    r = fc(target)
    r += ftext("Cl")
    return all(abs(l.get(k, 0) - r.get(k, 0)) < 1e-6 for k in set(l) | set(r))


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

    def run(smi, target):
        prods = eng.step([Compound(smiles=smi, name="x", herb="test")],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit, balance(smi, target)

    for label, smi, target in (
            ("STD", "ClCCCN1CCCC1", "C1CC[N+]2(C1)CCC2"),
            ("EXT", BY[EXTERNAL]["reactants"][0], BY[EXTERNAL]["product"])):
        prods, hit, bal = run(smi, target)
        ok = bool(hit) and bal
        print("%-4s %-4s products=%d hit=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, len(prods), len(hit), bal))
        fails += 0 if ok else 1

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
