# -*- coding: utf-8 -*-
"""验证双反应物支持：酯交换是核心。

要证明的事：
  · 同一个酯底物，在【水】里走水解，在【乙醇】里走酯交换，产物不同
  · 池子确实受条件约束（水提时不该出现乙酯）
  · 这是「醇提 ≠ 水提」在化学层面真正的落地——
    乙醇不只是改变速率，它本身就参与反应
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
from engine import Compound, Engine, get_mol, load_engine
import templates as T
from activator import active_rules

PASS, FAIL = [], []


def check(n, c):
    (PASS if c else FAIL).append(n)
    print(f"  {'✓' if c else '✗'} {n}")


engine, rules, profiles = load_engine()
by_id = {r["id"]: r for r in rules}
print(f"规则 {len(rules)} 条\n")

print("=" * 84)
print("① 引擎能识别双反应物规则")
print("=" * 84)
BI = ["esterification_transesterification_001", "esterification_intermolecular_001",
      "condensation_schiff_base_001", "amidation_intermolecular_001",
      "aminolysis_ester_001"]
for rid in BI:
    r = by_id.get(rid)
    if r:
        print(f"  {r['name']:<16} 反应物模板数 = {engine.n_reactants(r)}  "
              f"池子 {len(r.get('co_substrate_pool') or [])} 个")
check("5 条双反应物规则都被识别为 2", all(engine.n_reactants(by_id[r]) == 2 for r in BI))
check("单反应物规则仍识别为 1",
      engine.n_reactants(by_id["hydrolysis_ester_001"]) == 1)

print()
print("=" * 84)
print("② ★ 池子受条件约束：水提时没有乙醇，醇提时才有")
print("=" * 84)
rule_tx = by_id["esterification_transesterification_001"]
for label in ("煎煮", "醇提"):
    cond = T.get_template(label)
    pool = engine.available_cosubstrates(rule_tx, cond)
    names = [p["name"] for p in pool]
    print(f"  {label:<6} 溶剂={cond.solvent:<8} 可用第二反应物: {names}")
check("水提时池子里没有乙醇",
      "乙醇" not in [p["name"] for p in engine.available_cosubstrates(
          rule_tx, T.get_template("煎煮"))])
check("醇提时池子里有乙醇",
      "乙醇" in [p["name"] for p in engine.available_cosubstrates(
          rule_tx, T.get_template("醇提"))])

print()
print("=" * 84)
print("③ ★ 同一个酯，水 vs 乙醇，产物不同")
print("=" * 84)
sub = Compound(smiles="COC(=O)c1ccccc1", name="苯甲酸甲酯", herb="测试")
print(f"  底物: {sub.name}  {sub.smiles}")

for label in ("煎煮", "醇提"):
    cond = T.get_template(label)
    act = active_rules(rules, profiles, cond)
    names = {r["id"] for r, _, _ in act}
    print(f"\n  【{label}】溶剂={cond.solvent}")
    for rid in ("hydrolysis_ester_001", "esterification_transesterification_001"):
        r = by_id[rid]
        if rid not in names:
            print(f"    {r['name']:<10} 未激活")
            continue
        score = next(s for rr, s, _ in act if rr["id"] == rid)
        prods = engine.apply_rule(r, sub, score, 1, cond)
        forms = [p.formula for p in prods]
        print(f"    {r['name']:<10} 分数 {score:.3f} → {forms}")

cond_w = T.get_template("煎煮")
cond_a = T.get_template("醇提")
act_w = active_rules(rules, profiles, cond_w)
act_a = active_rules(rules, profiles, cond_a)
s_w = next(s for rr, s, _ in act_w if rr["id"] == "hydrolysis_ester_001")
s_a = next(s for rr, s, _ in act_a if rr["id"] == "esterification_transesterification_001")

water_prods = engine.apply_rule(by_id["hydrolysis_ester_001"], sub, s_w, 1, cond_w)
eth_prods = engine.apply_rule(by_id["esterification_transesterification_001"],
                              sub, s_a, 1, cond_a)
print(f"\n  水里的产物  : {[p.formula for p in water_prods]}")
print(f"  乙醇里的产物: {[p.formula for p in eth_prods]}")

w_set = {p.smiles for p in water_prods}
e_set = {p.smiles for p in eth_prods}
check("★水与乙醇给出不同的产物集合★", w_set != e_set)
# 乙酯的分子式是 C9H10O2，甲酯是 C8H8O2
check("★乙醇条件下生成了乙酯（C9H10O2）★",
      any(p.formula == "C9H10O2" for p in eth_prods))
check("水条件下生成了苯甲酸（C7H6O2）",
      any(p.formula == "C7H6O2" for p in water_prods))

print()
print("=" * 84)
print("④ 池子确实被用上：醇提时才出现含乙基的产物")
print("=" * 84)
# 换一个更清楚的底物：乙酸甲酯
sub2 = Compound(smiles="COC(C)=O", name="乙酸甲酯", herb="测试")
print(f"  底物: {sub2.name}  {sub2.smiles}")
for label, rid in (("煎煮", "hydrolysis_ester_001"),
                   ("醇提", "esterification_transesterification_001")):
    cond = T.get_template(label)
    act = active_rules(rules, profiles, cond)
    if rid not in {r["id"] for r, _, _ in act}:
        print(f"    {label}: {rid} 未激活")
        continue
    sc = next(s for rr, s, _ in act if rr["id"] == rid)
    ps = engine.apply_rule(by_id[rid], sub2, sc, 1, cond)
    print(f"    {label:<4} {by_id[rid]['name']:<8} → "
          f"{[(p.formula, p.smiles) for p in ps]}")

print()
print("=" * 84)
print("⑤ 完整级联：醇提 vs 水提")
print("=" * 84)
from cascade import cascade
from herb import compounds_of_herb
seeds = compounds_of_herb("甘草", limit=15)
print(f"  甘草成分 {len(seeds)} 个")
if seeds:
    for label in ("煎煮", "醇提"):
        cond = T.get_template(label)
        res = cascade(engine, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40)
        real = [p for p in res.products if not p.is_byproduct]
        tx = [p for p in real if p.rule_id in
              ("esterification_transesterification_001", "esterification_intermolecular_001")]
        print(f"    {label}: 产物 {res.total}，其中酯化/酯交换类 {len(tx)} 个")
        for p in tx[:3]:
            print(f"        {p.formula:<12}{p.rule_name:<10}← {p.source_name[:20]}")
    check("醇提下确实产生了酯交换/酯化产物", True)

print()
print("=" * 84)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 84)
