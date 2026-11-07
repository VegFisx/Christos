# -*- coding: utf-8 -*-
# 一次性：测"正向引擎单步跑一条反应"的耗时，决定 50k 正向评估的抽样规模。
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
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs", STAGE / "tools",
           STAGE / "conditions"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger                       # noqa: E402
RDLogger.DisableLog("rdApp.*")
from engine import Compound                            # noqa: E402
from smartreact_engine import SmartReactEngine         # noqa: E402
import templates as T                                  # noqa: E402

rows = []
for i, line in enumerate(open(STAGE / "reports" / "paper" / "data"
                              / "uspto50k_canon.jsonl", encoding="utf-8")):
    if line.strip():
        rows.append(json.loads(line))
    if i >= 5000:
        break

eng = SmartReactEngine()
cond = T.get_template("煎煮")
sample = random.Random(0).sample(rows, 20)
t0 = time.time()
n_hit = 0
for r in sample:
    comps = [Compound(smiles=s, name="R%d" % j, herb="(bench)")
             for j, s in enumerate(r["reactants"])]
    prods = eng.step(comps, cond, round_no=1)
    ss = {getattr(p, "smiles", None) for p in prods}
    n_hit += 1 if r["product"] in ss else 0
dt = time.time() - t0
print("20 条反应：%.1fs（%.0f ms/反应）· 命中 %d/20" % (dt, 1000 * dt / 20, n_hit))
print("外推：2,000 条 ≈ %.0f 分钟（单进程）→ 6 进程 ≈ %.0f 分钟"
      % (dt / 20 * 2000 / 60, dt / 20 * 2000 / 60 / 6))
