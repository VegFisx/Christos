# -*- coding: utf-8 -*-
r"""
追查：为什么甘草次酸 / 乌头原碱 没出现在产物里？

这是中医化学里最重要的一对减毒产物：
  甘草次酸 = 甘草酸 - 2×葡萄糖醛酸（苷元，抗炎活性成分）
  乌头原碱 = 乌头碱 - 乙酸 - 苯甲酸（附子减毒核心）

要分清三种可能：
  A 源成分里就没有甘草酸 / 乌头碱
  B 有，但单步水解出不来苷元（需要多步，而级联断了）
  C 规则本身产不出
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


def has_sub(smi, q):
    m = Chem.MolFromSmiles(smi) if smi else None
    qq = Chem.MolFromSmiles(q)
    return bool(m and qq and m.HasSubstructMatch(qq))


print("=" * 100)
print("① 源成分里有没有甘草酸 / 乌头碱")
print("=" * 100)
TARGETS = {
    "甘草酸": ("CC1(C)C(OC2OC(C(=O)O)C(O)C(O)C2OC2OC(C(=O)O)C(O)C(O)C2O)CCC2(C)C1CC=C1C3=CC(=O)C4(C)CCC"
              "(C)(C(=O)O)C4C3(C)CCC12C", "甘草"),
    "乌头碱": ("CCN1CC2(COC)C(OC(=O)c3ccccc3)CC(OC)C34C5CC6(OC(C)=O)C(OC)C(O)C(OC)C(C5C6OC)C2C13",
               "附子"),
}
for name, (smi, herb) in TARGETS.items():
    rows = find_compounds(herb, limit=200)
    hit = None
    for rr in rows:
        if canon(rr.get("smiles")) == canon(smi):
            hit = rr
            break
    # 再试子结构（可能是盐/衍生物）
    subhits = [rr for rr in rows if has_sub(rr.get("smiles"), smi)]
    print(f"  {name}（{herb} {len(rows)} 个成分）：")
    print(f"      精确命中: {'有 → ' + str(hit.get('name')) if hit else '无'}")
    print(f"      子结构命中 {len(subhits)} 个: "
          f"{[s.get('name')[:28] for s in subhits[:5]]}")

print()
print("=" * 100)
print("② 手工用「糖苷水解」跑甘草酸，看能不能出苷元")
print("=" * 100)
r_gly = next(x for x in rules if x["id"] == "hydrolysis_glycoside_001")
GA = TARGETS["甘草酸"][0]
s = Compound(smiles=GA, name="甘草酸", herb="甘草")
ps = eng.apply_rule(r_gly, s, 0.8, 1, cond)
print(f"  甘草酸 + 糖苷水解 → {len(ps)} 个产物")
for p in ps:
    print(f"      {p.formula:<16}{p.smiles[:66]}")

print()
print("=" * 100)
print("③ 手工用「酯水解」跑乌头碱")
print("=" * 100)
r_est = next(x for x in rules if x["id"] == "hydrolysis_ester_001")
AC = TARGETS["乌头碱"][0]
s2 = Compound(smiles=AC, name="乌头碱", herb="附子")
ps2 = eng.apply_rule(r_est, s2, 0.8, 1, cond)
print(f"  乌头碱 + 酯水解 → {len(ps2)} 个产物")
for p in ps2:
    print(f"      {p.formula:<16}{p.smiles[:66]}")

print()
print("=" * 100)
print("④ 从真实药材池跑一轮，看这两个母体产出了什么")
print("=" * 100)
for herb, mother, rule_id in (("甘草", GA, "hydrolysis_glycoside_001"),
                              ("附子", AC, "hydrolysis_ester_001")):
    rows = find_compounds(herb, limit=200)
    # 找池子里与母体最像的那个
    best = None
    m0 = Chem.MolFromSmiles(mother)
    for rr in rows:
        m = Chem.MolFromSmiles(rr.get("smiles") or "")
        if m is None:
            continue
        # 用分子式近似匹配
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        if CalcMolFormula(m) == CalcMolFormula(m0):
            best = rr
            break
    if best is None:
        print(f"  {herb}: 池子里没有与 {mother[:20]}… 同分子式的成分")
        continue
    print(f"  {herb} 里的 {best['name'][:34]}（分子式同）")
    r = next(x for x in rules if x["id"] == rule_id)
    sub = Compound(smiles=best["smiles"], name=best["name"], herb=herb)
    ps3 = eng.apply_rule(r, sub, 0.8, 1, cond)
    print(f"      {r['name']} → {len(ps3)} 个产物")
    for p in ps3[:4]:
        print(f"          {p.formula:<16}{p.smiles[:60]}")
