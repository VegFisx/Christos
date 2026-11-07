# -*- coding: utf-8 -*-
r"""
追查（修正版）：用数据库里真实的名字找母体，别用手写 SMILES。

上一版我用自己敲的 SMILES 去找甘草酸/乌头碱，结果一个都没匹配上 ——
而我明明在甘草成分表里见过 `Glycyrrhizin`。
**手写复杂天然产物 SMILES 不现实，必须用数据库里的真名。**
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")
from engine import Compound, get_mol, load_engine
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds
import templates as T

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


def find_by_name(herb, *keys, limit=300):
    out = []
    for rr in find_compounds(herb, limit=limit):
        nm = (rr.get("name") or "").lower()
        if any(k.lower() in nm for k in keys):
            out.append(rr)
    return out


print("=" * 100)
print("① 用名字找母体")
print("=" * 100)
GANCAO = find_by_name("甘草", "glycyrrhizin", "glycyrrhizic")
FUZI = find_by_name("附子", "aconitine")
print(f"  甘草里的甘草酸类: {[(r['name'][:34], r['smiles'][:28] + '…') for r in GANCAO[:4]]}")
print(f"  附子里的乌头碱类: {[(r['name'][:34], r['smiles'][:28] + '…') for r in FUZI[:4]]}")

if not FUZI:
    # 换名字找
    FUZI = find_by_name("附子", "aconit", "hypaconit", "mesaconit")
    print(f"  改关键字后: {[(r['name'][:34]) for r in FUZI[:6]]}")

print()
print("=" * 100)
print("② 对每个真实母体，逐条规则看能产出什么")
print("=" * 100)


def probe(herb, row, rule_ids):
    sub = Compound(smiles=row["smiles"], name=row["name"], herb=herb)
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    m = Chem.MolFromSmiles(row["smiles"])
    print(f"\n  【{row['name'][:40]}】{CalcMolFormula(m) if m else '?'}  "
          f"重原子 {m.GetNumHeavyAtoms() if m else '?'}")
    for rid in rule_ids:
        r = next((x for x in rules if x["id"] == rid), None)
        if r is None:
            continue
        ps = eng.apply_rule(r, sub, 0.8, 1, cond)
        if ps:
            print(f"      {r['name']:<18}→ {len(ps)} 个")
            for p in ps[:3]:
                print(f"            {p.formula:<16}{p.smiles[:58]}")

GLY_RULES = ["hydrolysis_glycoside_001", "hydrolysis_ester_001",
             "hydrolysis_acetal_001", "hydrolysis_hemiacetal_001"]
ACO_RULES = ["hydrolysis_ester_001", "hydrolysis_amide_001",
             "hydrolysis_acetal_001", "hydrolysis_hemiacetal_001",
             "elimination_dehydration_001"]

for row in GANCAO[:2]:
    probe("甘草", row, GLY_RULES)
for row in FUZI[:2]:
    probe("附子", row, ACO_RULES)

print()
print("=" * 100)
print("③ 目标产物能不能在这些结果里找到")
print("=" * 100)
TARGET_SUB = {
    "甘草次酸骨架（C30 五环三萜，C11=O，C30 羧酸）":
        "CC1(C)C(=O)C=C2C3=CCC4C5(C)CCC(C)(C(=O)O)C5CCC4(C)C3(C)CCC12C",
    "乌头原碱骨架（C19 二萜生物碱，多羟基，无酯基）":
        "CCN1CC2(COC)C(O)CC(OC)C34C5CC6(O)C(O)C(O)C(OC)C(C5C6O)C2C13",
}
for label, q in TARGET_SUB.items():
    qm = Chem.MolFromSmiles(q)
    if qm is None:
        print(f"  ? {label}  (查询 SMILES 解析失败)")
        continue
    hits = []
    for row in (GANCAO + FUZI):
        m = Chem.MolFromSmiles(row["smiles"])
        if m and m.HasSubstructMatch(qm):
            hits.append(row["name"])
    print(f"  {'✓' if hits else '—'} {label}")
    print(f"      母体命中: {[h[:34] for h in hits]}")
