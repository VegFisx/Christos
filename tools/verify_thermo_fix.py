# -*- coding: utf-8 -*-
r"""验证修复效果：水解产物不再被错误的 ΔG 压低。

对比：
  修复前（不加 thermo_unreliable）→ 水解产物拿到正的 ΔG → stability 很低 → 排序被压低
  修复后                          → 跳过 → 回退启发式 → 不再被冤枉

做法：直接看 assign_thermo 对水解类产物做了什么。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
from cascade import cascade
from thermo import Thermo
from scorer import assign_thermo
import json
import templates as T
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
rule_by_id = {r["id"]: r for r in rules}

print("=" * 92)
print("① 标记本身")
print("=" * 92)
marked = [r["name"] for r in rules if r.get("thermo_unreliable")]
print(f"  thermo_unreliable 规则 {len(marked)} 条: {marked}")
print(f"  水解类共 {sum(1 for r in rules if r.get('category')=='hydrolysis' and r.get('status')!='disabled')} 条，"
      f"其中标记 {sum(1 for r in rules if r.get('category')=='hydrolysis' and r.get('thermo_unreliable'))} 条")

print()
print("=" * 92)
print("② assign_thermo 对水解产物做了什么")
print("=" * 92)

# 造一批水解产物 + 一批非水解产物
class P:
    def __init__(self, rid, smi, src, co):
        self.rule_id = rid
        self.smiles = smi
        self.source_smiles = src
        self.co_products = co
        self.dg_kj = None
        self.stability = None
        self.score = 0.8

CASES = [
    ("糖苷水解", "hydrolysis_glycoside_001", "OC1OC(CO)C(O)C(O)C1O",
     "COC1OC(CO)C(O)C(O)C1O", ("OC1OC(CO)C(O)C(O)C1O", "CO")),
    ("酯水解", "hydrolysis_ester_001", "CC(=O)O",
     "CC(=O)OCC", ("CC(=O)O", "CCO")),
    ("环氧化物开环", "hydrolysis_epoxide_001", "OCCO", "C1CO1", ("OCCO",)),
    ("烯烃水合", "hydration_alkene_001", "CCO", "C=C", ("CCO",)),
]
prods = [P(rid, smi, src, co) for _n, rid, smi, src, co in CASES]

th = Thermo(n_conf=2)
stats = assign_thermo(prods, th, rule_by_id)
print(f"  统计: {stats}")
print()
print(f"  {'规则':<16}{'ΔG':>10}{'stability':>11}   说明")
print("  " + "-" * 62)
for (name, rid, smi, src, co), p in zip(CASES, prods):
    dg = f"{p.dg_kj:>10.1f}" if p.dg_kj is not None else f"{'跳过':>10}"
    st = f"{p.stability:>11.3f}" if p.stability is not None else f"{'—':>11}"
    why = ("★已跳过（气相 ΔG 符号系统性错误）" if p.dg_kj is None
           else "保留 ΔG 信号")
    print(f"  {name:<16}{dg}{st}   {why}")

print()
print("=" * 92)
print("③ 端到端：真实方剂上，水解产物是否还被压低")
print("=" * 92)
comps = []
for h in ("甘草",):
    for r in find_compounds(h, limit=12):
        comps.append(dict(r))
seeds = [Compound(smiles=c["smiles"], name=c["name"], herb=c["herb_name"])
         for c in comps if get_mol(c["smiles"])]
cond = T.get_template("酸水解")
res = cascade(eng, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40,
              thermo=Thermo(n_conf=2))
ts = res.thermo_stats or {}
print(f"  thermo_stats: {ts}")
print(f"  skipped_unreliable = {ts.get('skipped_unreliable', 0)}"
      f"   ← 被跳过的水解类产物")

# 看水解产物有没有 ΔG
hyd = [p for p in res.products if p.rule_id.startswith("hydrolysis_")
       and not p.is_byproduct]
n_dg = sum(1 for p in hyd if p.dg_kj is not None)
print(f"  水解类产物 {len(hyd)} 个，其中拿到 ΔG 的 {n_dg} 个"
      f"  {'✓ 已全部跳过' if n_dg == 0 else '✗ 仍有残留'}")
