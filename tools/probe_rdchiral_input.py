# -*- coding: utf-8 -*-
r"""探针：rdchiral.extract_from_reaction 到底要什么输入？（打印原始异常，不猜）"""
import sys, traceback
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
import rdchiral.template_extractor as te
print("rdchiral 路径:", te.__file__)
print("VERBOSE 默认:", getattr(te, "VERBOSE", None))
te.VERBOSE = True
from rdchiral.template_extractor import extract_from_reaction

CASES = [
    ("旧格式 reactants/product 字符串",
     {"reactants": "CC(=O)O.CCN", "product": "CCNC(C)=O", "_id": "t1"}),
    ("新格式 reaction_smiles",
     {"reaction_smiles": "CC(=O)O.CCN>>CCNC(C)=O", "_id": "t2"}),
    ("带映射的新格式",
     {"reaction_smiles": "[CH3:1][C:2](=[O:3])[OH:4].[CH3:5][CH2:6][NH2:7]>>[CH3:1][C:2](=[O:3])[NH:7][CH2:6][CH3:5]", "_id": "t3"}),
]
for label, d in CASES:
    print("=" * 88)
    print(label)
    print("  输入 keys:", list(d.keys()))
    try:
        r = extract_from_reaction(d)
        print("  OK ->", str(r)[:400])
    except Exception as e:
        print(f"  异常 {type(e).__name__}: {e}")
        traceback.print_exc()

print("=" * 88)
print("函数签名:", te.extract_from_reaction.__doc__)
import inspect
print(inspect.signature(te.extract_from_reaction))
src = inspect.getsource(te.extract_from_reaction)
print(src[:1800])
