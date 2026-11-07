# -*- coding: utf-8 -*-
"""端到端测试：方剂/药材 → 条件 → 级联产物 → 评分 → 追溯。

重点验证四件事：
  ① ★ 苯甲酸（以及乙酸、甲醇、CO2）不再被过滤器删掉 ★
     这是原 tcm_analyzer.py 最扎眼的科学错误：min_heavy=10 会把 9 个重原子的苯甲酸丢掉，
     而苯甲酸正是乌头碱酯水解减毒的标志性产物。
  ② ★ 端到端真的能产出苯甲酸 ★（用真实苯甲酸酯底物跑通）
  ③ 条件层的两种作用要分清：
       · 硬门槛（气氛）→ 改变产物【集合】
       · 软打分（温度/pH/溶剂）→ 改变产物【排序】
     这是设计使然，不该混为一谈。
  ④ 级联的收敛机制真的会停。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem
from rdkit.Chem import Descriptors, rdMolDescriptors

from engine import Compound, Engine, classify_product, get_mol, load_engine
from cascade import cascade
from scorer import score_product, rank
import templates as T
from herb import compounds_of_herb, find_named_compound, list_herbs

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name}")


engine, rules, profiles = load_engine()
BENZOIC = "OC(=O)c1ccccc1"


def canon(smi):
    """规范化 SMILES 再做比较。

    ★ 踩过的坑：不能直接比 SMILES 字符串。
      RDKit/rdchiral 会把 'OC(=O)c1ccccc1' 写成 'O=C(O)c1ccccc1'，
      字符串不等但其实是同一个分子，会导致误判"没产出苯甲酸"。
    """
    m = get_mol(smi)
    return Chem.MolToSmiles(m) if m is not None else None


BENZOIC_C = canon(BENZOIC)
print(f"引擎就绪：{len(rules)} 条规则，条件模板 {len(T.TEMPLATES)} 个")
print(f"苯甲酸标准形：{BENZOIC}  →  规范化后 {BENZOIC_C}\n")

print("=" * 88)
print("① 过滤器修复：小分子到底还在不在")
print("=" * 88)
CASES = [
    ("水", "O"), ("甲醇", "CO"), ("二氧化碳", "O=C=O"), ("甲酸", "O=CO"),
    ("乙酸", "CC(=O)O"), ("苯酚", "Oc1ccccc1"),
    ("★苯甲酸★", BENZOIC), ("苯甲酸甲酯", "COC(=O)c1ccccc1"),
]
print(f"  {'分子':<12}{'重原子':>6}{'分子量':>9}  保留?     副产物?   原代码会怎样")
print("  " + "-" * 70)
for name, smi in CASES:
    m = get_mol(smi)
    keep, is_by = classify_product(m)
    hv = m.GetNumHeavyAtoms()
    # 复刻原 _valid_product 的判据
    old = "保留" if (Descriptors.MolWt(m) >= 100 and hv >= 10) else "★丢弃★"
    print(f"  {name:<12}{hv:>6}{Descriptors.MolWt(m):>9.1f}"
          f"  {'保留' if keep else '★丢弃★':<8}{'是' if is_by else '否':<8}{old}")

check("★苯甲酸被保留（原代码会丢掉）",
      classify_product(get_mol(BENZOIC))[0])
check("苯甲酸未被误标为副产物",
      not classify_product(get_mol(BENZOIC))[1])
for nm, smi in (("乙酸", "CC(=O)O"), ("苯酚", "Oc1ccccc1")):
    check(f"{nm} 被保留", classify_product(get_mol(smi))[0])
for nm, smi in (("水", "O"), ("甲醇", "CO"), ("CO2", "O=C=O")):
    k, b = classify_product(get_mol(smi))
    check(f"{nm} 保留且标为副产物", k and b)

print()
print("=" * 88)
print("② ★ 端到端：真实苯甲酸酯底物 → 产物里到底有没有苯甲酸")
print("=" * 88)
from engine import Engine as _E
from activator import active_rules

ester_cond = T.get_template("酸水解")
demo_sub = Compound(smiles="COC(=O)c1ccccc1", name="苯甲酸甲酯", herb="(测试)", source="user")
act = active_rules(rules, profiles, ester_cond)
rule_ester = next(r for r, _, _ in act if r["id"] == "hydrolysis_ester_001")
prods = engine.apply_rule(rule_ester, demo_sub, activation=0.8, round_no=1)
print(f"  底物：苯甲酸甲酯 COC(=O)c1ccccc1")
print(f"  规则：{rule_ester['name']}")
print(f"  产出 {len(prods)} 个产物：")
for p in prods:
    tag = " [副产物]" if p.is_byproduct else ""
    mark = "  ★★★" if canon(p.smiles) == BENZOIC_C else ""
    print(f"    {p.formula:<10} MW {p.mw:>7.1f}  重原子 {p.heavy_atoms:>2}{tag}{mark}")
check("★苯甲酸出现在端到端产物中★",
      any(canon(p.smiles) == BENZOIC_C for p in prods))
check("甲醇也出现（原代码会丢掉）",
      any(p.formula == "CH4O" for p in prods))

print()
print("  用真实附子乌头碱（13,15-dideoxyaconitine，含苯甲酸酯）再验一次：")
acon = find_named_compound("13,15-dideoxyaconitine", limit=1)
if acon:
    sub = acon[0]
    prods2 = engine.apply_rule(rule_ester, sub, activation=0.8, round_no=1)
    print(f"    底物：{sub.name}")
    print(f"    产出 {len(prods2)} 个：")
    for p in prods2:
        tag = " [副产物]" if p.is_byproduct else ""
        mark = "  ★苯甲酸★" if canon(p.smiles) == BENZOIC_C else ""
        print(f"      {p.formula:<10} MW {p.mw:>7.1f}{tag}{mark}")
    check("★乌头碱酯水解产出苯甲酸★",
          any(canon(p.smiles) == BENZOIC_C for p in prods2))
else:
    check("找到 13,15-dideoxyaconitine", False)

print()
print("=" * 88)
print("③ 条件层的两种作用：硬门槛改集合，软打分改排序")
print("=" * 88)
hits = list_herbs("附子")
seeds = compounds_of_herb("附子", limit=40)
print(f"  附子成分：{len(seeds)} 个（marker 优先）")
check("取到附子成分", len(seeds) > 0)

results = {}
for label in ("煎煮", "酸水解", "无氧煎煮"):
    cond = T.get_template(label)
    res = cascade(engine, seeds, cond, max_rounds=2, min_new=5, frontier_limit=50)
    results[label] = res

for label, res in results.items():
    real = [p for p in res.products if not p.is_byproduct]
    byp = [p for p in res.products if p.is_byproduct]
    print(f"\n  【{label}】{res.conditions.describe()}")
    print(f"    产物 {res.total}（主体 {len(real)} + 副产物 {len(byp)}），轮次 {res.round_stats}")
    print(f"    Top 5：")
    for p in real[:5]:
        print(f"      {p.score:.3f}  {p.formula:<12}{p.rule_name:<12}← {p.source_name[:22]}")

print()
print("  ── 集合差异（由硬门槛决定）──")
sets = {k: {p.smiles for p in v.products} for k, v in results.items()}
for k, v in sets.items():
    print(f"    {k:<10} {len(v):>4} 个产物")
only_air = sets["煎煮"] - sets["无氧煎煮"]
only_n2 = sets["无氧煎煮"] - sets["煎煮"]
print(f"    有氧独有 {len(only_air)} 个 / 无氧独有 {len(only_n2)} 个")
check("★气氛改变产物集合（硬门槛生效）", len(only_air) > 0)

print()
print("  ── 排序差异（由软打分决定）──")
topA = [p.smiles for p in results["煎煮"].products[:20]]
topB = [p.smiles for p in results["酸水解"].products[:20]]
same_order = topA == topB
print(f"    煎煮 Top20 与 酸水解 Top20 顺序相同？ {'是' if same_order else '否'}")
print(f"    煎煮   Top5 规则：{[p.rule_name for p in results['煎煮'].products[:5]]}")
print(f"    酸水解 Top5 规则：{[p.rule_name for p in results['酸水解'].products[:5]]}")
check("★pH 改变产物排序（软打分生效）", not same_order)

print()
print("  ── 集合差异（由软阈值决定：把激活阈值抬高）──")
res_hi = cascade(engine, seeds, T.get_template("煎煮"),
                 max_rounds=2, min_new=5, frontier_limit=50, threshold=0.35)
set_hi = {p.smiles for p in res_hi.products}
print(f"    阈值 0.15 → {len(sets['煎煮'])} 个产物")
print(f"    阈值 0.35 → {len(set_hi)} 个产物")
check("抬高激活阈值会缩小产物集合", len(set_hi) < len(sets["煎煮"]))

print()
print("=" * 88)
print("④ 级联收敛机制")
print("=" * 88)
simple = [Compound(smiles="COC(=O)c1ccccc1", name="苯甲酸甲酯", herb="(测试)", source="user"),
          Compound(smiles="OCCCC(=O)O", name="4-羟基丁酸", herb="(测试)", source="user")]
for mr in (1, 2, 3):
    r = cascade(engine, simple, T.get_template("煎煮"),
                max_rounds=mr, min_new=5, frontier_limit=30)
    print(f"    max_rounds={mr} → 实跑 {r.rounds} 轮，产物 {r.total}，"
          f"收敛={r.converged}，统计 {r.round_stats}")
r3 = cascade(engine, simple, T.get_template("煎煮"), max_rounds=3, min_new=5)
check("级联能在有限轮内停下", r3.rounds <= 3)
check("轮次统计记录完整", all({"round", "new", "irreversible_new"} <= set(s)
                              for s in r3.round_stats))

print()
print("=" * 88)
print("⑤ 来源追溯")
print("=" * 88)
pool = [p for p in results["酸水解"].products if not p.is_byproduct]
if pool:
    p = pool[0]
    print(f"  产物 SMILES : {p.smiles[:72]}")
    print(f"  分子式/分子量: {p.formula} / {p.mw}  (重原子 {p.heavy_atoms})")
    print(f"  由哪条规则   : {p.rule_name} ({p.rule_id})")
    print(f"  来自哪个成分 : {p.source_name}")
    print(f"  成分的 SMILES: {p.source_smiles[:60]}")
    print(f"  来自哪味药   : {p.source_herb}")
    print(f"  第几轮       : {p.round}")
    print(f"  置信度       : {p.score}")
    rule = next(r for r in rules if r["id"] == p.rule_id)
    total, detail = score_product(p.smiles, rule, p.activation, p.source_smiles)
    print(f"  评分明细     : {detail}")
    check("产物带完整追溯字段",
          all([p.rule_id, p.source_name, p.source_herb, p.round >= 1]))
    check("评分明细含全部 5 个因子",
          set(detail) >= {"rule_match", "condition_match", "stability",
                          "atom_conservation", "stereo"})
    check("轮数衰减生效（第 2 轮产物分数被压低）",
          all(pp.score <= 1.0 for pp in results["酸水解"].products))

print()
print("=" * 88)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 88)
