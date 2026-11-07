# -*- coding: utf-8 -*-
r"""瓶颈定位：score_product / classify_product / get_mol 各占多少时间？"""
from __future__ import annotations

import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from scorer import score_product                     # noqa: E402
from engine import classify_product, get_mol         # noqa: E402
from smartreact_engine import SmartReactEngine       # noqa: E402
import templates as T                                # noqa: E402
from herb import compounds_of_herb                   # noqa: E402

seeds = compounds_of_herb("甘草", limit=4)
cond = T.get_template("煎煮")
eng = SmartReactEngine(gate_conditions=True, use_extra_templates=False, verbose=False)
t0 = time.time()
prods = eng.step(seeds, cond, 0.15, round_no=1)
print(f"引擎单步（4 底物）：产物 {len(prods)}  耗时 {time.time()-t0:.2f}s", flush=True)

rule_by_id = eng._rule_by_id
sample = prods[:40]
print(f"对前 {len(sample)} 个产物逐个计时：", flush=True)

t0 = time.time()
for p in sample:
    get_mol(p.smiles)
t_getmol = time.time() - t0

t0 = time.time()
for p in sample:
    classify_product(get_mol(p.smiles))
t_class = time.time() - t0

t0 = time.time()
for p in sample:
    score_product(p.smiles, rule_by_id.get(p.rule_id, {}), 1.0,
                  source_smiles=p.source_smiles)
t_score = time.time() - t0

n = len(sample)
print(f"  get_mol          {t_getmol:7.2f}s  ({t_getmol/n*1000:8.1f} ms/产物)", flush=True)
print(f"  classify_product {t_class:7.2f}s  ({t_class/n*1000:8.1f} ms/产物)", flush=True)
print(f"  score_product    {t_score:7.2f}s  ({t_score/n*1000:8.1f} ms/产物)  ← 嫌疑", flush=True)
print(f"\n  ★ 若 score_product 是几百 ms/产物：2000 个产物就是十几分钟 —— 与实测吻合。", flush=True)

# 拆解 score_product 内部
import inspect  # noqa: E402
src = inspect.getsource(score_product)
print("\nscore_product 源码行数：", len(src.splitlines()), flush=True)
for ln in src.splitlines():
    s = ln.strip()
    if any(k in s for k in ("xtb", "thermo", "Conformer", "EmbedMolecule", "MMFF",
                            "ComputeGasteiger", "Descriptors.", "GetSubstruct",
                            "rdMolDescriptors", "for ", "def ")):
        print("   ", s[:110], flush=True)
