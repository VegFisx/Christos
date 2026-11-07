# -*- coding: utf-8 -*-
"""rxnmapper 实跑（用 RXNMapper）。"""
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))

from rxnmapper import RXNMapper

print("=== 首次会从 HuggingFace 下模型（约 350MB），请等 ===")
t0 = time.time()
m = RXNMapper()
print(f"  模型加载耗时 {time.time()-t0:.1f}s")

RXNS = [
    ("酰胺缩合", "CC(=O)O.CCN>>CC(=O)NCC"),
    ("对二酚氧化", "Oc1ccc(O)cc1.O=O>>O=C1C=CC(=O)C=C1"),
    ("酯水解", "CC(=O)OCC.O>>CC(=O)O.CCO"),
    ("糖苷水解", "COC1OC(CO)C(O)C(O)C1O.O>>OC1OC(CO)C(O)C(O)C1O.CO"),
]
print()
t0 = time.time()
try:
    res = m.get_attention_guided_atom_maps([r for _n, r in RXNS])
    for (name, r), out in zip(RXNS, res):
        print(f"  【{name}】{r}")
        print(f"      映射   {out['mapped_rxn']}")
        print(f"      置信度 {out['confidence']:.3f}")
    print(f"\n  {len(RXNS)} 条反应总耗时 {time.time()-t0:.1f}s "
          f"（平均 {(time.time()-t0)/len(RXNS):.2f}s/条，CPU）")
except Exception as e:
    import traceback
    print(f"  ✗ {type(e).__name__}: {str(e)[:300]}")
    traceback.print_exc()
