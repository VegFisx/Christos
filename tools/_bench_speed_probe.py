# -*- coding: utf-8 -*-
# 一次性：测"全套模板 × 单个产物"的实际耗时，用来决定 5 万条是全跑/并行/抽样。
import json
import random
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                        # noqa: E402
import retro_search as rs                               # noqa: E402

RDLogger.DisableLog("rdApp.*")

lib = rs.load_rdchiral_templates()
print("模板 %d 条" % len(lib), flush=True)

prods = []
for i, line in enumerate(open(STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl",
                              encoding="utf-8")):
    prods.append(json.loads(line)["product"])
    if i >= 20000:
        break
sample = random.Random(0).sample(prods, 40)

total_cuts = 0
t0 = time.time()
t_apply = 0.0
for smi in sample:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        continue
    t1 = time.time()
    for t in lib:
        try:
            outs = t.rxn.RunReactants((m,))
        except Exception:
            continue
        total_cuts += len(outs)
    t_apply += time.time() - t1
dt = time.time() - t0
print("40 个产物 × %d 模板：总耗时 %.1fs（每次套用 %.2f ms）· 产出切断 %d（%.1f/产物）"
      % (len(lib), dt, 1000 * t_apply / (40 * len(lib)), total_cuts, total_cuts / 40))
print("外推：50,000 产物 ≈ %.0f 分钟（单进程）" % (dt / 40 * 50000 / 60))
