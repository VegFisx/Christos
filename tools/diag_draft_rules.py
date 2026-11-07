# -*- coding: utf-8 -*-
"""诊断 7 条「匹配不到任何底物」的草稿规则：是 SMARTS 错了，还是分子本来就少？"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolDescriptors
from schema import load_rules, atom_counts, formula_atoms, add_atoms, atom_diff, format_atoms

profiles, rules = load_rules(STAGE / "rules" / "rules.json")
by_id = {r["id"]: r for r in rules}

# 每条规则配一个"化学上应该能匹配"的手工底物
PROBES = {
    "hydrolysis_imine_001": [],
    "decarboxylation_malonic_001": [
        ("丙二酸", "OC(=O)CC(=O)O"),
        ("乙酰乙酸", "CC(=O)CC(=O)O"),
    ],
    "elimination_decarboxylation_phenol_001": [
        ("水杨酸", "OC(=O)c1ccccc1O"),
        ("咖啡酸", "OC(=O)/C=C/c1ccc(O)c(O)c1"),
        ("没食子酸", "OC(=O)c1cc(O)c(O)c(O)c1"),
    ],
    "cyclization_hemiacetal_001": [
        ("4-羟基丁醛", "O=CCCCO"),
        ("5-羟基戊醛", "O=CCCCCO"),
        ("葡萄糖(开链)", "OCC(O)C(O)C(O)C(=O)O"),
    ],
    "cyclization_lactam_001": [
        ("4-氨基丁酸", "NCCCC(=O)O"),
        ("5-氨基戊酸", "NCCCCC(=O)O"),
    ],
    "condensation_aldol_intra_001": [
        ("5-氧代己醛", "O=CCCC(=O)C"),
        ("2,5-己二酮", "CC(=O)CCC(=O)C"),
    ],
    "oxidation_thiol_disulfide_001": [
        ("半胱氨酸", "NC(CS)C(=O)O"),
        ("谷胱甘肽类似物", "SCC(N)C(=O)O"),
    ],
    "reduction_nitro_001": [
        ("硝基苯", "O=[N+]([O-])c1ccccc1"),
        ("硝基甲烷", "C[N+](=O)[O-]"),
    ],
}

for rid, probes in PROBES.items():
    r = by_id.get(rid)
    if r is None:
        continue
    print("=" * 84)
    print(f"【{r['name']}】{rid}")
    print(f"  SMARTS: {r['smarts']}")
    try:
        rx = AllChem.ReactionFromSmarts(r["smarts"])
        print(f"  rdkit 编译: OK")
    except Exception as e:
        print(f"  rdkit 编译: ✗ {e}")
        continue
    from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
    try:
        rr = rdchiralReaction(r["smarts"])
        print(f"  rdchiral 接受: OK")
    except Exception as e:
        print(f"  rdchiral 拒绝: ✗ {str(e)[:90]}")
        continue

    if not probes:
        print("  （未配探针）")
        continue

    co = formula_atoms(r.get("co_reagents"), "co")
    by = formula_atoms(r.get("byproducts"), "by")
    for name, smi in probes:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            print(f"    {name:<16} SMILES 无效")
            continue
        try:
            outs = rdchiralRun(rr, rdchiralReactants(smi)) or []
        except Exception as e:
            print(f"    {name:<16} rdchiral 抛异常: {str(e)[:60]}")
            continue
        if not outs:
            print(f"    {name:<16} 不匹配")
            continue
        left = add_atoms(atom_counts(mol), co)
        for out in outs[:2]:
            right = dict(by)
            frags = []
            for part in out.split("."):
                pm = Chem.MolFromSmiles(part)
                if pm is None:
                    continue
                right = add_atoms(right, atom_counts(pm))
                frags.append(rdMolDescriptors.CalcMolFormula(pm))
            d = atom_diff(left, right)
            print(f"    {name:<16} → {' + '.join(frags):<32} "
                  f"{'配平' if not d else '★失衡 ' + str(d) + '★'}")
    print()
