# -*- coding: utf-8 -*-
r"""
真实底物用例：底物【取自 tcm.db】，期望产物【来自化学常识】。
================================================================

用户指出的问题：验收用例的底物是我手写的，不是数据库里的真实药材成分。
目标里写的是「**真实底物用例**」。

本模块的设计原则：
  1. 底物一律按【名字】从 tcm.db 取 —— 找不到就报错，我无法悄悄替换
  2. 期望产物用【分子式】写 —— 因为手写复杂天然产物 SMILES 已经错过三次
  3. 期望值来自化学常识/文献，不是"照着引擎输出抄一遍"

先跑一个探测，看数据库里有哪些可用母体。
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
from rdkit.Chem.rdMolDescriptors import CalcMolFormula
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

# 想找的母体（按名字关键字）
WANTED = [
    ("甘草", ["glycyrrhizin", "glycyrrhizic acid"], "甘草酸"),
    ("附子", ["aconitine"], "乌头碱"),
    ("附子", ["hypaconitine"], "次乌头碱"),
    ("大黄", ["sennoside"], "番泻苷"),
    ("甘草", ["liquiritin"], "甘草苷"),
    ("甘草", ["rutin", "isorhamnetin"], "芦丁类"),
    ("大黄", ["emodin"], "大黄素"),
    ("黄芩", ["baicalin"], "黄芩苷"),
]

print("=" * 100)
print("数据库里可用的母体（按名字找，不手写 SMILES）")
print("=" * 100)
FOUND = {}
for herb, keys, label in WANTED:
    rows = find_compounds(herb, limit=300)
    hits = []
    for rr in rows:
        nm = (rr.get("name") or "").lower()
        if any(k.lower() in nm for k in keys):
            m = Chem.MolFromSmiles(rr.get("smiles") or "")
            if m:
                hits.append((rr["name"], CalcMolFormula(m),
                             m.GetNumHeavyAtoms(), rr["smiles"]))
    FOUND[label] = hits
    print(f"\n  【{label}】{herb} 命中 {len(hits)} 个")
    for nm, f, heavy, smi in hits[:4]:
        print(f"      {nm[:42]:<44}{f:<14}重原子 {heavy}")
