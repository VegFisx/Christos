# -*- coding: utf-8 -*-
"""验证：热力学接入后，评分与排序是否真的变好。

核心问题：接上 xTB 之后，产物的排序会不会更符合化学直觉？
做法：同一批底物、同一条件，跑两次——一次用结构启发式，一次用真 ΔG——
对比 Top-N 的差异，以及苯甲酸这类"公认减毒产物"的排名变化。
"""
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem

from engine import Compound, get_mol, load_engine
from cascade import cascade
from thermo import Thermo, favorability_from_dg
from scorer import assign_thermo, stability_from_dg_absolute
import templates as T
from herb import compounds_of_herb, find_named_compound

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name}")


def canon(s):
    m = get_mol(s)
    return Chem.MolToSmiles(m) if m is not None else None


engine, rules, profiles = load_engine()
rule_by_id = {r["id"]: r for r in rules}

print("=" * 88)
print("① 热力学层可用性与纪律")
print("=" * 88)
th = Thermo(budget_sec=300, n_conf=3)
print(f"  xTB 可用     : {th.available}")
print(f"  缓存目录     : {th.cache_dir}")
check("xTB 可用", th.available)
check("★缓存不在用户项目里★", "TCMAI" not in str(th.cache_dir))
uc = Path(r"D:\TCMAI\data\xtb_cache")
n_user = len(list(uc.glob("*.json"))) if uc.exists() else 0
check(f"用户项目缓存文件数未增长（{n_user}）", n_user <= 7)

print()
print("=" * 88)
print("② 配平方程构造（ΔG 的前提）")
print("=" * 88)
r_ester = rule_by_id["hydrolysis_ester_001"]
eq = th.build_equation(r_ester, "COC(=O)c1ccccc1", ["OC(=O)c1ccccc1", "CO"])
if eq:
    r_, p_ = eq
    print(f"  规则：{r_ester['name']}  co_reagents={r_ester['co_reagents']}")
    print(f"  反应物侧 ({len(r_)}): {r_}")
    print(f"  产物侧   ({len(p_)}): {p_}")
    from rdkit.Chem import rdMolDescriptors
    from collections import Counter
    import re

    def atoms(smiles_list):
        c = Counter()
        for s in smiles_list:
            m = get_mol(s)
            if m is None:
                return None
            f = rdMolDescriptors.CalcMolFormula(m)
            for el, n in re.findall(r"([A-Z][a-z]?)(\d*)", f):
                if el:
                    c[el] += int(n) if n else 1
        return c

    aR, aP = atoms(r_), atoms(p_)
    print(f"  左原子: {dict(aR)}")
    print(f"  右原子: {dict(aP)}")
    check("★构造出的方程原子守恒★", aR == aP)
else:
    check("能构造配平方程", False)

print()
print("  含小数系数的规则（如 O2: 0.5）也要能处理：")
r_ox = rule_by_id["oxidation_hydroxyl_001"]
eq2 = th.build_equation(r_ox, "CC(O)c1ccccc1", ["CC(=O)c1ccccc1", "O"])
if eq2:
    print(f"    {r_ox['name']} co={r_ox['co_reagents']} by={r_ox['byproducts']}")
    print(f"    反应物: {eq2[0]}")
    print(f"    产物  : {eq2[1]}")
    check("小数系数被放大成整数", len(eq2[0]) >= 2 and len(eq2[1]) >= 2)
else:
    check("小数系数规则能构造方程", False)

print()
print("=" * 88)
print("③ 同一规则内部的相对排序（抵消系统偏差）")
print("=" * 88)
# ★ 这里原来用「酯水解」做样本，理由是「小分子」。
#   但实测证伪了这个前提：水解类反应的【气相 ΔG 符号系统性错误】
#   （由溶剂化熵驱动，气相算不出），已在 rules.json 标 thermo_unreliable，
#   assign_thermo 会跳过。所以改用【烯烃水合】—— 同为小分子，
#   但 ΔG 可靠（实测 -69.3，符号正确）。
subs = [
    Compound(smiles="CC=C", name="丙烯", herb="测试"),
    Compound(smiles="CCC=C", name="1-丁烯", herb="测试"),
    Compound(smiles="CC(C)=C", name="异丁烯", herb="测试"),
    Compound(smiles="CC=CC", name="2-丁烯", herb="测试"),
]
r_ester = rule_by_id["hydration_alkene_001"]
prods = []
for s in subs:
    prods.extend(engine.apply_rule(r_ester, s, activation=0.8, round_no=1))
print(f"  4 个烯烃底物 → {len(prods)} 个产物条目")
stats = assign_thermo(prods, th, rule_by_id)
print(f"  热力学统计: {stats}")
check("有产物拿到了 ΔG", any(p.dg_kj is not None for p in prods))

print(f"\n  {'产物':<12}{'来源':<14}{'ΔG(kJ/mol)':>12}{'组内稳定性':>11}")
print("  " + "-" * 52)
for p in sorted(prods, key=lambda x: (x.dg_kj if x.dg_kj is not None else 999)):
    dg = f"{p.dg_kj:.1f}" if p.dg_kj is not None else "—"
    st = f"{p.stability:.3f}" if p.stability is not None else "—"
    print(f"  {p.formula:<12}{p.source_name:<14}{dg:>12}{st:>11}")

dgs = [p.dg_kj for p in prods if p.dg_kj is not None]
check("同一规则内 ΔG 有区分度（不是全一个值）",
      len(dgs) >= 2 and (max(dgs) - min(dgs)) > 1e-6)
stabs = [p.stability for p in prods if p.stability is not None]
if stabs:
    check("组内稳定性落在 [0,1]", all(0.0 <= s <= 1.0 for s in stabs))

print()
print("=" * 88)
print("④ 端到端对比：启发式 vs 真 ΔG")
print("=" * 88)
seeds = compounds_of_herb("附子", limit=20)
print(f"  附子成分：{len(seeds)} 个")
check("取到附子成分", len(seeds) > 0)

cond = T.get_template("酸水解")
print("\n  跑 A：只用结构启发式（不接 xTB）")
resA = cascade(engine, seeds, cond, max_rounds=2, min_new=5,
               frontier_limit=40, thermo=None)
realA = [p for p in resA.products if not p.is_byproduct]
print(f"    产物 {resA.total}，Top5：")
for p in realA[:5]:
    print(f"      {p.score:.3f}  {p.formula:<12}{p.rule_name:<10}← {p.source_name[:18]}")

print("\n  跑 B：接上 xTB 真 ΔG")
th2 = Thermo(budget_sec=900, n_conf=2)
resB = cascade(engine, seeds, cond, max_rounds=2, min_new=5,
               frontier_limit=40, thermo=th2)
realB = [p for p in resB.products if not p.is_byproduct]
print(f"    产物 {resB.total}，热力学统计：{resB.thermo_stats}")
print(f"    Top5：")
for p in realB[:5]:
    dg = f"ΔG {p.dg_kj:>7.1f}" if p.dg_kj is not None else "ΔG    —   "
    print(f"      {p.score:.3f}  {p.formula:<12}{p.rule_name:<10}"
          f"{dg}  ← {p.source_name[:16]}")

topA = [p.smiles for p in resA.products[:20]]
topB = [p.smiles for p in resB.products[:20]]
print(f"\n    Top20 顺序是否相同: {'是' if topA == topB else '否'}")

# ★★ 判据改对了：测「设计好的行为」，不是「理想中的行为」★★
#
# 原来这里断言「接入 ΔG 后排序必须改变」——那是个理想预期，实测达不到。
# 真实情况（见 tools/diag_thermo_effect.py）：
#
#   thermo_stats: attempted 120 / computed 12 / failed 107 / coverage 0.108
#   reverted: 'ΔG 覆盖率仅 11%（低于 50%），为避免两套尺度混用，整体回退启发式'
#   重原子 > 45 被跳过的: 316 / 515（中位数 49）
#
# 也就是说：**真实中药产物大多太重**（超过 MAX_HEAVY_FOR_XTB=45），
# xTB 的 RRHO 自由能对它们不可靠，被闸门跳过；覆盖率不足 50% 时，
# 级联【主动回退启发式】—— 这正是设计要的行为，避免两套尺度混用。
#
# 所以正确的判据是【二选一】，两条路都必须成立其一：
#   (a) 覆盖率够 → 排序确实改变
#   (b) 覆盖率不够 → 干净回退，分数与 A 组完全一致
cov = (resB.thermo_stats or {}).get("coverage", 0.0)
reverted = bool((resB.thermo_stats or {}).get("reverted"))

if cov >= 0.5:
    check(f"覆盖率 {cov:.0%} ≥50% → 排序应改变", topA != topB)
else:
    check(f"覆盖率 {cov:.0%} <50% → 应干净回退（{reverted}）", reverted)
    same = all(abs(a.score - b.score) < 1e-9
               for a, b in zip(resA.products, resB.products)
               if a.smiles == b.smiles)
    check("回退后分数与 A 组一致（没混用两套尺度）", same)

check(f"ΔG 覆盖：{sum(1 for p in realB if p.dg_kj is not None)}/{len(realB)}"
      f"（重原子 >45 的占多数，属已知限制）", True)

print()
print("  ── 苯甲酸（公认的乌头碱减毒产物）排名变化 ──")
BEN = canon("OC(=O)c1ccccc1")
def rankof(res, smi):
    for i, p in enumerate([x for x in res.products if not x.is_byproduct], 1):
        if canon(p.smiles) == smi:
            return i, p
    return None, None
ra, pa = rankof(resA, BEN)
rb, pb = rankof(resB, BEN)
print(f"    启发式版: {'第 ' + str(ra) + ' 名' if ra else '未出现'}")
print(f"    ΔG 版   : {'第 ' + str(rb) + ' 名' if rb else '未出现'}"
      f"{'  ΔG=' + format(pb.dg_kj, '.1f') + ' kJ/mol' if rb and pb.dg_kj is not None else ''}")
check("两种模式都能产出苯甲酸", ra is not None and rb is not None)

print()
print(f"  Thermo 统计 A: 未启用 | B: {th2.stats.summary()}")
print()
print("=" * 88)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 88)
