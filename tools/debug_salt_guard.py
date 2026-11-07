# -*- coding: utf-8 -*-
"""查盐类底物为什么还在被守卫拦。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem

SALT = "C=CCCCCCCCCC(=O)[O-].[Na+]"
m = Chem.MolFromSmiles(SALT)
print("SMILES:", SALT)
print("解析成功:", m is not None)
print("片段数:", len(Chem.GetMolFrags(m)))
print("重原子:", m.GetNumAtoms())
for i, frag in enumerate(Chem.GetMolFrags(m)):
    print(f"  片段{i}: {frag}")

from engine import get_mol, _atom_counts_of_smiles
mm = get_mol(SALT)
print("\nget_mol 片段数:", len(Chem.GetMolFrags(mm)) if mm else None)
print("_atom_counts_of_smiles:", _atom_counts_of_smiles(SALT))

print()
print("=== 逐规则定位是哪一步在丢 ===")
from engine import Compound, load_engine
import templates as T
eng, rules, profs = load_engine()
r2 = next(x for x in rules if x["id"] == "reduction_alkene_001")
print("rule smarts:", r2["smarts"], " status:", r2.get("status"))
print("co_reagents:", r2.get("co_reagents"), "byproducts:", r2.get("byproducts"))
print("n_reactants:", eng.n_reactants(r2))
sub = Compound(smiles=SALT, name="salt", herb="t")
cond = T.get_template("还原")
from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
outs = rdchiralRun(rdchiralReaction(r2["smarts"]), rdchiralReactants(SALT)) or []
print("rdchiral 产物组:", outs)
before = getattr(eng, "balance_dropped", 0)
ps = eng.apply_rule(r2, sub, 0.6, 1, cond)
print("产物:", [(p.smiles, p.formula) for p in ps])
print("守卫增量:", getattr(eng, "balance_dropped", 0) - before)
