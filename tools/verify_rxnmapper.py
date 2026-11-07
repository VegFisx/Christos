# -*- coding: utf-8 -*-
"""验证 rxnmapper 装好且能用（CPU）。"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

import rdkit
import torch
print("  rdkit   :", rdkit.__version__, " <- 必须 2026.03.6")
print("  torch   :", torch.__version__)
print("  CUDA    :", torch.cuda.is_available())

for m in ("rxnmapper", "transformers", "smartreact", "ord_schema",
          "rxn.chemutils", "duckdb", "polars"):
    try:
        mod = __import__(m)
        v = getattr(mod, "__version__", "")
        print(f"  OK      {m:<16}{v}")
    except Exception as e:
        print(f"  FAIL    {m:<16}{type(e).__name__}: {str(e)[:55]}")

# 真的跑一次原子映射（会下载小模型，第一次慢）
print()
print("=== 实跑 rxnmapper（首次会下载模型）===")
try:
    from rxnmapper import RxnMapper
    m = RxnMapper()
    rxn = "CC(=O)O.CCN>>CC(=O)NCC"
    import time
    t0 = time.time()
    res = m.get_attention_guided_atom_maps([rxn])
    dt = time.time() - t0
    print(f"  输入 {rxn}")
    print(f"  映射 {res[0]['mapped_rxn']}")
    print(f"  置信度 {res[0].get('confidence'):.3f}   耗时 {dt:.1f}s")
except Exception as e:
    import traceback
    print(f"  ✗ {type(e).__name__}: {str(e)[:200]}")
