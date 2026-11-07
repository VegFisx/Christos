
# -*- coding: utf-8 -*-
import hashlib, json, sys
from pathlib import Path
STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core","conditions","rules","libs","sources"):
    p = STAGE/d
    if p.is_dir(): sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error"); RDLogger.DisableLog("rdApp.warning")
from engine import Compound, get_mol, load_engine
from cascade import cascade
import templates as T
from activator import active_rules
import compat
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")
import os
QUICK = os.environ.get("DSH_QUICK") == "1"
HERBS = ("甘草",) if QUICK else ("甘草","附子")
PER = 8 if QUICK else 12
comps = []
for h in HERBS:
    for r in find_compounds(h, limit=PER):
        comps.append(dict(r))
subs = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
        for c in comps if get_mol(c["smiles"])]

out = {}

# ① step：有序序列（含分数、来源、规则）
ps = eng.step(subs, cond, 0.15, round_no=1)
seq = [f"{p.smiles}|{p.rule_id}|{p.source_smiles}|{p.score:.10f}" for p in ps]
out["step_order"] = hashlib.sha256("\n".join(seq).encode()).hexdigest()[:16]
out["step_n"] = len(seq)

# ② cascade：有序序列 + 轮次
r2 = cascade(eng, subs, cond, max_rounds=4, min_new=8, frontier_limit=30)
cseq = [f"{p.smiles}|{p.rule_id}|{p.round}|{p.score:.10f}" for p in r2.products]
out["cascade_order"] = hashlib.sha256("\n".join(cseq).encode()).hexdigest()[:16]
out["cascade_n"] = len(cseq)
out["cascade_rounds"] = r2.rounds

# ③ 兼容层
pr = compat.predict_reactions(comps)
pseq = [f"{p['smiles']}|{p['rxn']}|{p['from_compound']}|{p['mw']}" for p in pr]
out["predict_order"] = hashlib.sha256("\n".join(pseq).encode()).hexdigest()[:16]
out["predict_n"] = len(pseq)

# ④ 多样性排序 Top-20（模拟前端）
main = [p for p in r2.products if not p.is_byproduct]
import types
from predict import PredictionResult
shell = types.SimpleNamespace(products=main)
top = PredictionResult.diverse_ranking(shell, top=20)
tseq = [f"{p.smiles}|{p.rule_id}" for p in top]
out["top20_order"] = hashlib.sha256("\n".join(tseq).encode()).hexdigest()[:16]
out["top20_n"] = len(tseq)

# ⑤ 激活规则顺序
act = active_rules(rules, profs, cond, 0.15)
aseq = [f"{r['id']}|{s:.10f}" for r, s, _w in act]
out["active_order"] = hashlib.sha256("\n".join(aseq).encode()).hexdigest()[:16]
out["active_n"] = len(aseq)

print("PROBE " + json.dumps(out, ensure_ascii=False))
