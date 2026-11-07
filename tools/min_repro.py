# -*- coding: utf-8 -*-
r"""最小可复现脚本：只做一件事——跑一次 step，打印产物数。
用于跨进程重复执行，判断是不是真有不确定性。
"""
import sys
from pathlib import Path
import os

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

# ★ 快速模式：只缩小输入，判据不变 ★
#   跨进程审计要把本脚本跑 3~6 遍，所以它的输入大小直接决定审计耗时。
#   缩小输入不会降低"能不能发现不确定性"的能力 —— 只要有一条产物不同就会露馅。
QUICK = os.environ.get("DSH_QUICK") == "1"
HERBS = ("甘草",) if QUICK else ("甘草", "附子", "干姜")
PER = 10 if QUICK else 20

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
import templates as T
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


eng, rules, profs = load_engine()
cond = T.get_template("煎煮")
comps = []
for h in HERBS:
    for r in find_compounds(h, limit=PER):
        comps.append(dict(r))
subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in comps if get_mol(c["smiles"])]
ps = eng.step(subs, cond, 0.15, round_no=1)
s = {canon(p.smiles) for p in ps}
s.discard(None)

import hashlib
joined = "\n".join(sorted(s)).encode("utf-8")
print(f"COUNT {len(s)}  SUBSTRATES {len(subs)}  "
      f"HASH {hashlib.sha256(joined).hexdigest()[:16]}")
