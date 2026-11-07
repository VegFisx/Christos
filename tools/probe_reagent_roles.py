# -*- coding: utf-8 -*-
r"""一次性探针：角色 SMARTS 认得对不对（判零靠它，错一个就会误杀）。

对每个已知试剂打印：canonical SMILES + 命中的角色。人眼扫一遍即可判断。
用法: python probe_reagent_roles.py
"""
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "libs"):
    sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from smartreact_engine import REAGENT_ROLE_SMARTS, SmartReactEngine  # noqa: E402

RDLogger.DisableLog("rdApp.*")

REAGENT_ALIAS = SmartReactEngine.REAGENT_ALIAS

ROLES = [(n, Chem.MolFromSmarts(s)) for n, s in REAGENT_ROLE_SMARTS]
TEST = [
    ("PPh3", "P(c1ccccc1)(c1ccccc1)c1ccccc1", "phosphine"),
    ("PBu3", "CCCCP(CCCC)CCCC", "phosphine"),
    ("DEAD", "CCOC(=O)/N=N/C(=O)OCC", "azodicarboxylate"),
    ("DIAD", "CC(C)OC(=O)/N=N/C(=O)OC(C)C", "azodicarboxylate"),
    ("DCC(别名表)", REAGENT_ALIAS["dcc"], "carbodiimide"),
    ("DCC(长名)", REAGENT_ALIAS["dicyclohexylcarbodiimide"], "carbodiimide"),
    ("EDC", "CCN=C=NCCCN(C)C", "carbodiimide"),
    ("HATU", REAGENT_ALIAS["hatu"], "uronium_activator"),
    ("HOBt(别名表)", REAGENT_ALIAS["hobt"], "benzotriazole"),
    ("K2CO3", REAGENT_ALIAS["k2co3"], "无"),
    ("Et3N", REAGENT_ALIAS["et3n"], "无"),
    ("PPh3O(氧化态)", "O=P(c1ccccc1)(c1ccccc1)c1ccccc1", "无"),
    ("水", REAGENT_ALIAS["water"], "无"),
]
print("=" * 96)
print("角色 SMARTS 实测（原文表在 core/smartreact_engine.py: REAGENT_ROLE_SMARTS）")
print("=" * 96)
bad = 0
for label, smi, expect in TEST:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        print(f"  !! {label:<22} SMILES 解析失败: {smi}")
        bad += 1
        continue
    hits = [n for n, p in ROLES if p is not None and m.HasSubstructMatch(p)]
    canon = Chem.MolToSmiles(m)
    ok = "OK " if (expect in hits or (expect == "无" and not hits)) else "?? "
    if ok == "?? ":
        bad += 1
    print(f"  {ok}{label:<22} -> {hits}   期望 {expect}")
    print(f"      canon={canon}")
print()
print(f"存疑 {bad} 条")
