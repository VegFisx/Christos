# -*- coding: utf-8 -*-
"""专用验证：protection_boc_azole_001（唑类 N-H 的 Boc 保护）。

检查：
  · 3 个标准唑 + Boc2O 的正例；
  · 3 条 295 外部探针中的 held-out 案例（未用于规则设计）；
  · 负例（苯胺、吡啶、苯、Boc2O 自身）不得命中；
  · 主产物 + t-BuOH + CO2 的分子式配平。

用法：
    python tools\\validate_boc_azole.py
"""
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

RID = "protection_boc_azole_001"
BOC = "CC(C)(C)OC(=O)OC(=O)OC(C)(C)C"
CASES = json.loads((ROOT / "data" / "holdout_general_organic_295_20261123.json")
                   .read_text(encoding="utf-8"))["cases"]
BY = {c["id"]: c for c in CASES}
EXTERNAL = ["uspto50k_test_US08569494B2", "uspto50k_test_US20070244173A1",
            "uspto50k_test_US20100130446A1"]
POS_STANDARD = [
    ("imidazole", "c1ncc[nH]1", "CC(C)(C)OC(=O)n1ccnc1"),
    ("pyrrole", "c1cc[nH]c1", "CC(C)(C)OC(=O)n1cccc1"),
    ("triazole", "c1n[nH]cn1", "CC(C)(C)OC(=O)n1cncn1"),
]
NEG = [
    ("aniline", "Nc1ccccc1"),
    ("pyridine", "n1ccccc1"),
    ("benzene", "c1ccccc1"),
]


def canon(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""


def key(s):
    m = Chem.MolFromSmiles(s or "")
    if m is None:
        return ""
    try:
        from rdkit.Chem import inchi
        return inchi.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def fcount(f):
    f = (f or "").replace("+", "").replace("-", "")
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", f):
        out[e] += float(n or 1)
    return out


def balance(reactants, product):
    left = Counter()
    for s in reactants:
        m = Chem.MolFromSmiles(s)
        if m is None:
            return False
        for k, v in fcount(rdMolDescriptors.CalcMolFormula(m)).items():
            left[k] += v
    right = Counter()
    m = Chem.MolFromSmiles(product)
    if m is None:
        return False
    for k, v in fcount(rdMolDescriptors.CalcMolFormula(m)).items():
        right[k] += v
    for f, n in (("C4H10O", 1), ("CO2", 1)):
        for k, v in fcount(f).items():
            right[k] += v * n
    return all(abs(left.get(k, 0) - right.get(k, 0)) < 1e-6
               for k in set(left) | set(right))


def main():
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=[RID],
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
        allow_unvalidated=False,
    )
    cond = T.get_template("煎煮")
    fails = 0
    print(eng.curated_note)
    if len(eng.curated_pair_templates) != 1:
        print("FAIL rule not loaded as one pair template")
        fails += 1

    def run(reactants, target):
        prods = eng.step([Compound(smiles=s, name="x", herb="test") for s in reactants],
                         cond, round_no=1, exclude_smiles=set())
        want = key(target)
        hit = [p for p in prods if key(getattr(p, "smiles", "")) == want]
        return prods, hit

    for name, azole, target in POS_STANDARD:
        prods, hit = run([BOC, azole], target)
        ok = bool(hit) and balance([BOC, azole], target)
        print("%-4s POS %-24s products=%d balance=%s"
              % ("PASS" if ok else "FAIL", name, len(prods), balance([BOC, azole], target)))
        if not ok:
            fails += 1
            print("      got", [p.smiles[:80] for p in prods[:3]])

    for cid in EXTERNAL:
        c = BY[cid]
        prods, hit = run(c["reactants"], c["product"])
        ok = bool(hit) and balance(c["reactants"], c["product"])
        print("%-4s EXT %-24s products=%d balance=%s"
              % ("PASS" if ok else "FAIL", cid, len(prods), balance(c["reactants"], c["product"])))
        if not ok:
            fails += 1
            print("      got", [p.smiles[:80] for p in prods[:3]])

    for name, smi in NEG:
        prods, hit = run([BOC, smi], "CC(C)(C)O")
        ok = not prods
        print("%-4s NEG %-24s products=%d"
              % ("PASS" if ok else "FAIL", name, len(prods)))
        if not ok:
            fails += 1
            print("      unexpected", [p.smiles[:80] for p in prods[:3]])

    print("\nRESULT", "PASS" if not fails else "FAIL", "failures=%d" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
