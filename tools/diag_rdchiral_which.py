# -*- coding: utf-8 -*-
"""把让 rdchiral 抛异常的底物揪出来。"""
import sys
import traceback
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "rules"))
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem
from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
from schema import load_rules, _load_substrates

_, rules = load_rules(STAGE / "rules" / "rules.json")
BY_ID = {r["id"]: r for r in rules}

substrates = _load_substrates(r"D:\TCMAI\tcm.db", 4000)
print(f"底物总数: {len(substrates)}\n")

for rid in ("hydrolysis_amide_001", "oxidation_amine_001",
            "esterification_intramolecular_001"):
    rule = BY_ID[rid]
    tmpl = rule["smarts"].replace("!@", "")
    print("=" * 80)
    print(f"【{rule['name']}】 {rid}")
    print(f"  模板: {tmpl}")
    try:
        rxn = rdchiralReaction(tmpl)
    except Exception as e:
        print(f"  rdchiralReaction 失败: {e}")
        continue

    n_ok = n_empty = n_err = 0
    first_err = None
    for name, smiles, mol in substrates:
        if len(Chem.GetMolFrags(mol)) > 1:
            continue
        try:
            outs = rdchiralRun(rxn, rdchiralReactants(smiles))
            if outs:
                n_ok += 1
            else:
                n_empty += 1
        except Exception as e:
            n_err += 1
            if first_err is None:
                first_err = (name, smiles, e, traceback.format_exc())
    print(f"  有产物 {n_ok} | 无产物 {n_empty} | 抛异常 {n_err}")
    if first_err:
        name, smiles, e, tb = first_err
        print(f"  首个异常底物: {name}  {smiles[:80]}")
        print(f"  异常类型: {type(e).__name__}: {str(e)[:200]}")
        for line in tb.strip().splitlines()[-6:]:
            print(f"      {line}")
    print()
