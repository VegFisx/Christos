# -*- coding: utf-8 -*-
"""验证本轮 RXNMapper+RDChiral 派生的五条规则（不是手写 SMARTS）。

检查：
  · 正例（含第二底物泛化）；
  · 负例（产物/交叉糖/无关底物不反应）；
  · 配平（主产物 + 同批产物 = 底物）；
  · 目标按 InChIKey 前 14 位匹配（与 holdout 口径一致）。

用法：
    python tools\\validate_derived_rules.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

import query_base as qb
import validate_literature_conversions as V
from engine import Compound
from smartreact_engine import SmartReactEngine

DB = "file:D:/TCMAI/tcm.db?mode=ro"
RULES = [
    "isomerization_cyclic_ether_saponin_001",
    "rearrangement_strychnos_alkaloid_001",
    "oxidation_n_demethylation_aromatization_001",
    "dehydration_cyclization_hmf_fructose_001",
    "dehydration_cyclization_hmf_glucose_001",
]

# (rule, label, seed, target, condition)
POSITIVE = [
    (RULES[0], "SSa -> SSb1", "HBIN042787", "HBIN042789", "炮制·醋炙"),
    (RULES[0], "SSd -> SSb2 (second)", "HBIN042801", "HBIN042791", "炮制·醋炙"),
    (RULES[1], "strychnine -> isostrychnine", "HBIN045003", "HBIN031270", "炮制·炒黄"),
    (RULES[1], "brucine -> isobrucine (second)", "HBIN018923", "HBIN030507", "炮制·炒黄"),
    (RULES[2], "evodiamine -> rutaecarpine", "HBIN026264", "HBIN042657", "炮制·炒黄"),
    (RULES[3], "fructose -> 5-HMF", "HBIN026793", "HBIN029444", "炮制·蒸制"),
    (RULES[4], "glucose -> 5-HMF", "HBIN028037", "HBIN029444", "炮制·蒸制"),
]

NEGATIVE = [
    (RULES[0], "SSb1 (product)", "HBIN042789"),
    (RULES[1], "isostrychnine (product)", "HBIN031270"),
    (RULES[2], "rutaecarpine (product)", "HBIN042657"),
    (RULES[3], "glucose (cross-sugar)", "HBIN028037"),
    (RULES[4], "fructose (cross-sugar)", "HBIN026793"),
    (RULES[3], "sucrose", "HBIN045073"),
    (RULES[4], "sucrose", "HBIN045073"),
]


def db():
    return sqlite3.connect(DB, uri=True).cursor()


def row(cur, iid):
    return cur.execute(
        "SELECT name_en,formula,COALESCE(isomeric_smiles,smiles),inchi_key "
        "FROM compounds WHERE ingredient_id=?", (iid,)).fetchone()


def canon(s):
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m else ""


def key(s):
    try:
        return V.full_inchikey(s)[:14]
    except Exception:
        return ""


def fcount(f):
    f = (f or "").replace("+", "").replace("-", "")
    out = Counter()
    for e, n in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", f):
        out[e] += float(n or 1)
    return out


# 引擎会把模板里 3 个相同的水去重成 1 个 Product；配平按模板的 3 H2O 记。
EXTRA_BYPRODUCTS = {
    "dehydration_cyclization_hmf_fructose_001": {"H2O": 2},
    "dehydration_cyclization_hmf_glucose_001": {"H2O": 2},
}


def bal(seed_smi, product, rid):
    left = fcount(rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(seed_smi)))
    right = fcount(product.formula)
    for c in (product.co_products or ()):
        m = Chem.MolFromSmiles(c)
        if m is not None:
            for k, v in fcount(rdMolDescriptors.CalcMolFormula(m)).items():
                right[k] += v
    for f, n in EXTRA_BYPRODUCTS.get(rid, {}).items():
        for k, v in fcount(f).items():
            right[k] += v * n
    keys = set(left) | set(right)
    return all(abs(left.get(k, 0.0) - right.get(k, 0.0)) < 1e-6 for k in keys)


def main() -> int:
    cur = db()
    rules = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
    rules = rules.get("rules") if isinstance(rules, dict) else rules
    by_id = {r["id"]: r for r in rules if isinstance(r, dict)}
    missing = [r for r in RULES if r not in by_id]
    if missing:
        print("FAIL missing rules", missing)
        return 1
    eng = SmartReactEngine(
        use_curated_templates=True, curated_rule_ids=RULES,
        use_extra_templates=False, use_mono_templates=False,
        use_base_templates=False, rescue=False, stereo_enum_cap=0,
        gate_conditions=False, strict_redox_gate=False,
    )
    fails = 0
    cache = {}

    def step(rid, smi, cond_name):
        k = (rid, smi, cond_name)
        if k in cache:
            return cache[k]
        cond = qb.RunSpec(seeds=[], cond_name=cond_name).cond()
        prods = [p for p in eng.step([Compound(smiles=smi, name="probe")],
                                     cond, round_no=1, exclude_smiles=set())
                 if p.rule_id == rid]
        cache[k] = prods
        return prods

    for rid, label, sid, tid, cond_name in POSITIVE:
        s = row(cur, sid)
        t = row(cur, tid)
        prods = step(rid, s[2], cond_name)
        want = (t[3] or "")[:14]
        hit = [p for p in prods if key(p.smiles) == want]
        ok_bal = bool(prods) and all(bal(s[2], p, rid) for p in prods)
        ok = bool(hit) and ok_bal
        print("%-4s POS %-34s %-46s products=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, rid, len(prods), ok_bal))
        if not ok:
            fails += 1
            if not hit:
                print("      target", t[0], want, "got", [(p.rule_id, key(p.smiles)) for p in prods][:5])

    for rid, label, sid in NEGATIVE:
        s = row(cur, sid)
        prods = step(rid, s[2], "炮制·蒸制")
        ok = not prods
        print("%-4s NEG %-34s %-46s products=%d"
              % ("PASS" if ok else "FAIL", label, rid, len(prods)))
        if not ok:
            fails += 1
            print("      unexpected", [(p.rule_id, p.smiles[:80]) for p in prods][:5])

    print("\nRESULT", "PASS" if fails == 0 else "FAIL", "failures=%d" % fails)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
