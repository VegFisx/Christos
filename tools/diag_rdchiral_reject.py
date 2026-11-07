# -*- coding: utf-8 -*-
"""聚焦诊断：rdchiral 为什么拒绝 酰胺水解 / 胺氧化 / 酯化 这三条规则？"""
import sys
import traceback
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "rules"))
sys.path.insert(0, str(STAGE / "libs"))

from rdkit import Chem
from rdkit.Chem import AllChem
from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants
from schema import load_rules

_, rules = load_rules(STAGE / "rules" / "rules.json")
BY_ID = {r["id"]: r for r in rules}

TARGETS = [
    ("hydrolysis_amide_001", "酰胺水解", "CC(=O)Nc1ccccc1", "乙酰苯胺"),
    ("oxidation_amine_001", "胺氧化", "CCc1ccccc1N", "邻乙基苯胺"),
    ("esterification_intramolecular_001", "酯化", "OCCCC(=O)O", "4-羟基丁酸"),
]

print("=" * 82)
print("逐个尝试 rdchiralReaction / rdchiralRun，打印完整报错")
print("=" * 82)

for rid, name, substrate, sname in TARGETS:
    rule = BY_ID.get(rid)
    if rule is None:
        print(f"\n[{name}] 找不到规则 {rid}")
        continue
    smarts = rule["smarts"]
    smarts_noring = smarts.replace("!@", "")

    print(f"\n{'='*82}")
    print(f"【{name}】 {rid}")
    print(f"  当前 SMARTS : {smarts}")
    if smarts != smarts_noring:
        print(f"  去 !@ 后    : {smarts_noring}")
    print(f"  底物        : {sname}  {substrate}")

    for tag, tmpl in (("原样", smarts), ("去!@", smarts_noring)):
        if tag == "去!@" and smarts == smarts_noring:
            continue
        print(f"\n  ── 模板[{tag}] ──")
        # 1) rdkit 能否编译
        try:
            rxn_rd = AllChem.ReactionFromSmarts(tmpl)
            print(f"     rdkit 编译      : OK  "
                  f"({rxn_rd.GetNumReactantTemplates()} 反应物 / "
                  f"{rxn_rd.GetNumProductTemplates()} 产物模板)")
        except Exception as e:
            print(f"     rdkit 编译      : ✗ {str(e)[:90]}")

        # 2) rdchiral 能否接受
        try:
            rxn_rch = rdchiralReaction(tmpl)
            attrs = [a for a in dir(rxn_rch) if not a.startswith("_")]
            print(f"     rdchiralReaction: OK   属性={attrs}")
            for a in ("reactants", "products", "template", "smarts"):
                if hasattr(rxn_rch, a):
                    print(f"        {a} = {getattr(rxn_rch, a)!r}")
        except Exception as e:
            print(f"     rdchiralReaction: ✗ {type(e).__name__}: {str(e)[:160]}")
            continue

        # 3) 能否跑出产物
        try:
            reactants = rdchiralReactants(substrate)
            outs = rdchiralRun(rxn_rch, reactants)
            print(f"     rdchiralRun     : {outs if outs else '（无产物 / 不匹配）'}")
        except Exception as e:
            print(f"     rdchiralRun     : ✗ {type(e).__name__}: {str(e)[:200]}")
            tb = traceback.format_exc().strip().splitlines()
            for line in tb[-5:]:
                print(f"        {line}")

print()
print("=" * 82)
print("附加：rdchiral 对 '.' 和环闭合的容忍度测试")
print("=" * 82)
PROBES = [
    ("普通单产物",        "[CX3:1](=[OX1:2])[#6:3]>>[CX4:1]([OH])[#6:3]"),
    ("两片段产物",        "[C:1](=[O:2])[O:3][C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"),
    ("产物用新原子编号",  "[C:1](=[O:2])[N:3][C:4]>>[C:1](=[O:2])[O:5][H].[N:3][C:4]"),
    ("新原子上带显式H",   "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O:5].[N:2]"),
    ("新原子无H指定",     "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O:5].[N]"),
    ("带环闭合的产物",    "[OX2H:1][CX4:2][CX3:3](=[OX1:4])[OX2H:5]>>[O:1]1[CX4:2][CX3:3](=[OX1:4])[OH:5]1"),
    ("!@ 键约束",         "[C:1](=[O:2])[O:3]!@[C:4]>>[C:1](=[O:2])[O:3][H].[C:4][OH]"),
]
for label, tmpl in PROBES:
    try:
        rdchiralReaction(tmpl)
        print(f"  ✓ {label:<18} rdchiral 接受")
    except Exception as e:
        print(f"  ✗ {label:<18} {type(e).__name__}: {str(e)[:110]}")
