# -*- coding: utf-8 -*-
# 一次性：测"可用性判据"在 5 万条规模下的成本（40 个产物样本，全套模板 + step_usability）。
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
prods = []
for i, line in enumerate(open(STAGE / "reports" / "paper" / "data" / "uspto50k_canon.jsonl",
                              encoding="utf-8")):
    prods.append(json.loads(line)["product"])
    if i >= 20000:
        break
sample = random.Random(0).sample(prods, 40)

n_cut = n_usable = 0
t0 = time.time()
for smi in sample:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        continue
    for t in lib:
        try:
            outs = t.rxn.RunReactants((m,))
        except Exception:
            continue
        for tup in outs:
            prec = tuple(rs.canon(Chem.MolToSmiles(p)) for p in tup if p is not None)
            prec = tuple(p for p in prec if p)
            if not prec:
                continue
            ok, why = rs.step_usability(smi, prec)
            n_cut += 1
            if ok:
                n_usable += 1
dt = time.time() - t0
print("40 产物：切断 %d · 可用 %d（%.1f%%）· 总耗时 %.1fs（%.2f ms/切断）"
      % (n_cut, n_usable, 100.0 * n_usable / max(1, n_cut), dt, 1000 * dt / max(1, n_cut)))
print("USTAT:", {k: v for k, v in rs.USTAT.items() if v})
print("外推：50,000 产物 ≈ %.0f 分钟（单进程，含判据）" % (dt / 40 * 50000 / 60))
