# -*- coding: utf-8 -*-
"""专门验证本轮手写的两条通用规则。

只验证这两条：
  · oxidation_benzylic_alcohol_001
  · demethylation_aromatic_o_001

检查四件事：
  1. SMARTS 能编译、能在这两条规则自己的 engine 里应用；
  2. 正例：目标产物出现；副产物/辅试剂配平；
  3. 负例：结构相近的底物不反应（防过宽）；
  4. 独立验证集的两条已写规则案例在 evidence 口径命中（HMF 暂缓，标 SKIP）。

这是独立脚本，不读 30 例 holdout 的结果；期望表写死在这里。
用法：
    python tools\\validate_new_rules.py
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
from engine import Compound
from smartreact_engine import SmartReactEngine
from validate_literature_paths import run_once
import validate_literature_conversions as V

DB = "file:D:/TCMAI/tcm.db?mode=ro"

RULES = [
    "oxidation_benzylic_alcohol_001",
    "demethylation_aromatic_o_001",
]

# (rule_id, label, seed, target, condition)
POSITIVE = [
    (RULES[0], "benzyl alcohol", "OCc1ccccc1", "O=Cc1ccccc1", "炮制·蒸制"),
    (RULES[0], "4-hydroxybenzyl alcohol", "OCc1ccc(O)cc1", "O=Cc1ccc(O)cc1", "炮制·蒸制"),
    (RULES[1], "anisole", "COc1ccccc1", "Oc1ccccc1", "炮制·蒸制"),
    (RULES[1], "guaiacol", "COc1ccccc1O", "Oc1ccccc1O", "炮制·蒸制"),
    (RULES[1], "palmatine", "HBIN038666", "HBIN038670", "炮制·酒炙"),
    (RULES[1], "berberine", "HBIN017893", "pubchem:berberrubine", "炮制·酒炙"),
]

NEGATIVE = [
    (RULES[0], "ethanol", "CCO"),
    (RULES[0], "cyclohexanol", "OC1CCCCC1"),
    (RULES[0], "phenol", "Oc1ccccc1"),
    (RULES[0], "2-phenylethanol", "OCCc1ccccc1"),
    (RULES[0], "benzaldehyde", "O=Cc1ccccc1"),
    (RULES[1], "methanol", "CO"),
    (RULES[1], "ethanol", "CCO"),
    (RULES[1], "methyl benzoate", "COC(=O)c1ccccc1"),
    (RULES[1], "phenol", "Oc1ccccc1"),
]


def db():
    return sqlite3.connect(DB, uri=True).cursor()


def db_row(cur, iid):
    return cur.execute(
        "SELECT ingredient_id,name_en,formula,COALESCE(isomeric_smiles,smiles),inchi_key "
        "FROM compounds WHERE ingredient_id=?", (iid,)).fetchone()


def canon(smi):
    m = Chem.MolFromSmiles(smi)
    return Chem.MolToSmiles(m) if m else ""


def formula_counts(f):
    """C7H8O / C19H16NO4+ / H2O -> Counter；用于配平。"""
    f = (f or "").strip()
    f = f.replace("+", "").replace("-", "")
    out = Counter()
    for elem, num in re.findall(r"([A-Z][a-z]?)(\d*\.?\d*)", f):
        out[elem] += float(num or 1)
    return out


def _add(dst, src, mult=1.0):
    for k, v in (src or {}).items():
        dst[k] += float(v) * mult


def rule_balance(rule, seed_smi, products):
    """按反应类型检查配平；多甲氧基底物允许 n 次去甲基。

    苄位氧化：seed + 0.5 O2 == product + H2O。
    芳香 O-去甲基：每个大产物都应有 seed - n*CH2 的元素差，
    对应 n 次 ArOCH3 + H2O -> ArOH + CH3OH；甲醇等小产物跳过。
    """
    if not products:
        return False, {}
    seed = formula_counts(rdMolDescriptors.CalcMolFormula(Chem.MolFromSmiles(seed_smi)))
    rid = rule.get("id", "")

    if rid == "demethylation_aromatic_o_001":
        checked = 0
        diffs = {}
        for p in products:
            pc = formula_counts(p.formula)
            if pc.get("C", 0) <= 1:       # 甲醇等小产物
                continue
            n = seed.get("C", 0) - pc.get("C", 0)
            if n <= 0:
                diffs = {"C": n}
                continue
            exp = Counter(seed)
            exp["C"] -= n
            exp["H"] -= 2 * n
            keys = set(exp) | set(pc)
            d = {k: round(exp.get(k, 0.0) - pc.get(k, 0.0), 6) for k in keys}
            checked += 1
            if not all(abs(v) < 1e-6 for v in d.values()):
                diffs = d
        return checked > 0 and not any(abs(v) >= 1e-6 for v in diffs.values()), diffs

    # 苄位氧化：只取第一条主产物
    p = products[0]
    left = Counter(seed)
    for f, n in (rule.get("co_reagents") or {}).items():
        _add(left, formula_counts(f), float(n))
    right = formula_counts(p.formula)
    for f, n in (rule.get("byproducts") or {}).items():
        _add(right, formula_counts(f), float(n))
    keys = set(left) | set(right)
    diffs = {k: round(left.get(k, 0.0) - right.get(k, 0.0), 6) for k in keys}
    return all(abs(v) < 1e-6 for v in diffs.values()), diffs


def resolve_seed(cur, val):
    if str(val).startswith("HBIN"):
        row = db_row(cur, val)
        if not row:
            raise KeyError(val)
        return row[1], row[3]
    return val, val


def resolve_target(cur, val):
    if str(val).startswith("HBIN"):
        row = db_row(cur, val)
        if not row:
            raise KeyError(val)
        return canon(row[3])
    if str(val).startswith("pubchem:"):
        key = str(val).split(":", 1)[1]
        ts = json.loads((ROOT / "data" / "target_structures.json").read_text(encoding="utf-8"))
        rec = ts["compounds"][key]
        return canon(rec["smiles"])
    return canon(val)


def main() -> int:
    cur = db()
    rules = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
    rules = rules.get("rules") if isinstance(rules, dict) else rules
    by_id = {r["id"]: r for r in rules if isinstance(r, dict)}
    missing = [rid for rid in RULES if rid not in by_id]
    if missing:
        print("FAIL missing rules:", missing)
        return 1

    # 1) SMARTS 编译
    for rid in RULES:
        sm = by_id[rid].get("smarts", "")
        if not Chem.MolFromSmarts(sm.split(">>", 1)[0]):
            print("FAIL SMARTS compile:", rid, sm)
            return 1
        print("OK  SMARTS", rid)

    eng = SmartReactEngine(
        use_curated_templates=True,
        curated_rule_ids=RULES,
        use_extra_templates=False,
        use_mono_templates=False,
        use_base_templates=False,
        rescue=False,
        stereo_enum_cap=0,
        gate_conditions=False,
        strict_redox_gate=False,
    )

    failures = 0
    cache = {}

    def run_rule(rid, seed_smi, cond_name):
        key = (rid, seed_smi, cond_name)
        if key in cache:
            return cache[key]
        cond = qb.RunSpec(seeds=[], cond_name=cond_name).cond()
        prods = [p for p in eng.step([Compound(smiles=seed_smi, name="probe")],
                                     cond, round_no=1, exclude_smiles=set())
                 if p.rule_id == rid]
        cache[key] = prods
        return prods

    # 2) 正例
    for rid, label, seed, target, cond_name in POSITIVE:
        name, smi = resolve_seed(cur, seed)
        tgt = resolve_target(cur, target)
        prods = run_rule(rid, smi, cond_name)
        hit = [p for p in prods if canon(p.smiles) == tgt]
        ok_bal, diffs = rule_balance(by_id[rid], smi, prods) if prods else (False, {})
        ok = bool(hit) and ok_bal
        print("%-4s POS %-28s %-24s products=%d balance=%s"
              % ("PASS" if ok else "FAIL", label, rid, len(prods), ok_bal))
        if not ok:
            failures += 1
            if not hit:
                print("      target not found:", tgt, "got", [canon(p.smiles) for p in prods][:5])
            if prods and not ok_bal:
                print("      balance diffs:", {k: v for k, v in diffs.items() if abs(v) > 1e-6})

    # 3) 负例
    for rid, label, smi in NEGATIVE:
        prods = run_rule(rid, smi, "炮制·蒸制")
        ok = not prods
        print("%-4s NEG %-28s %-24s products=%d"
              % ("PASS" if ok else "FAIL", label, rid, len(prods)))
        if not ok:
            failures += 1
            print("      unexpected:", [(p.rule_id, canon(p.smiles)) for p in prods][:5])

    # 4) 独立验证集：两条已写规则在 evidence 口径命中；HMF 暂缓
    print("\nIndependent validation (evidence r1):")
    checks = [
        ("benzyl alcohol", "HBIN017844", "O=Cc1ccccc1", "炮制·蒸制"),
        ("berberine", "HBIN017893", None, "炮制·酒炙"),
    ]
    for label, iid, tgt_smi, cond_name in checks:
        row = db_row(cur, iid)
        hops, _sec = run_once((row[1], row[3], "independent"), cond_name=cond_name,
                              mode="evidence", rounds=1)
        if tgt_smi is None:
            ts = json.loads((ROOT / "data" / "target_structures.json").read_text(encoding="utf-8"))
            tgt_smi = ts["compounds"]["berberrubine"]["smiles"]
        tgt = canon(tgt_smi)
        hit = [h for h in hops if canon(h.product) == tgt]
        ok = bool(hit)
        print("%-4s IND %-28s %-24s hits=%s"
              % ("PASS" if ok else "FAIL", label, "evidence", [h.rule for h in hit][:3]))
        if not ok:
            failures += 1
    print("SKIP IND huangjing_glucose_hmf (HMF rule deferred by scope)")

    print("\nRESULT", "PASS" if failures == 0 else "FAIL", "failures=%d" % failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
