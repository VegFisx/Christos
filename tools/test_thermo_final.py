# -*- coding: utf-8 -*-
"""热力学层的最终结论测试：分两个场景，说清楚它「在哪有用、在哪没用」。

场景 A：小分子（酯类）——xTB 应当给出可用 ΔG 并真正参与排序
场景 B：中药大分子（附子乌头碱类）——覆盖率不足，应当正确整体回退

这个测试的目的不是证明"接入成功"，而是**划清热力学层的适用边界**。
"""
import sys
import time
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem
from engine import Compound, get_mol, load_engine
from cascade import cascade, MIN_THERMO_COVERAGE
from thermo import Thermo, MAX_HEAVY_FOR_XTB, DG_SANE_MIN, DG_SANE_MAX
from scorer import assign_thermo
import templates as T
from herb import compounds_of_herb

PASS, FAIL = [], []


def check(n, c):
    (PASS if c else FAIL).append(n)
    print(f"  {'✓' if c else '✗'} {n}")


def canon(s):
    m = get_mol(s)
    return Chem.MolToSmiles(m) if m is not None else None


engine, rules, profiles = load_engine()
rule_by_id = {r["id"]: r for r in rules}
th = Thermo(budget_sec=420, n_conf=2)

print("=" * 88)
print("场景 A：热力学层在哪【能】用 —— 判据是反应类型，不是分子大小")
print("=" * 88)
# ★ 场景 A 原来用的是「酯水解」，理由是「分子小所以 xTB 准」。
#   但实测把这个前提证伪了（tools/refine_hydrolysis_boundary.py）：
#     酯水解 +13.2 / 糖苷 +11.0 / 酰胺 +34.6 / 亚胺 +13.0 / 内酰胺 +88.3
#     —— 符号【系统性错误】，因为这些反应由溶剂化熵驱动，气相算不出。
#   而加成型/张力释放型是对的：
#     烯烃水合 -69.3 / 烯酮水合 -15.4 / 环氧化物开环 -28.5
#
#   所以判据是【反应类型】：水切断键 → 不可靠；水加成/开环 → 可靠。
#   场景 A 改用「烯烃水合」（小分子 + ΔG 可靠），
#   并额外验证「酯水解确实被跳过」。

r_hyd = rule_by_id["hydration_alkene_001"]
subs = [
    Compound(smiles="CC=C", name="丙烯", herb="测试"),
    Compound(smiles="CCC=C", name="1-丁烯", herb="测试"),
    Compound(smiles="CC(C)=C", name="异丁烯", herb="测试"),
    Compound(smiles="C=CC1CC1", name="乙烯基环丙烷", herb="测试"),
    Compound(smiles="CC=CC", name="2-丁烯", herb="测试"),
]
t0 = time.time()
prods = []
for s in subs:
    prods.extend(engine.apply_rule(r_hyd, s, activation=0.8, round_no=1))
st = assign_thermo(prods, th, rule_by_id)
dt = time.time() - t0
print(f"  {len(subs)} 个烯烃底物 → {len(prods)} 个产物条目，耗时 {dt:.1f}s")
print(f"  统计: {st}")
n_dg = sum(1 for p in prods if p.dg_kj is not None)
print(f"  拿到 ΔG 的: {n_dg}/{len(prods)}")
check(f"可靠反应类型 ΔG 覆盖率 > 70%（实测 {n_dg}/{len(prods)}）",
      n_dg >= len(prods) * 0.7)

print(f"\n  {'产物':<12}{'来源':<14}{'ΔG(kJ/mol)':>12}{'组内稳定性':>11}")
print("  " + "-" * 52)
for p in sorted(prods, key=lambda x: (x.dg_kj if x.dg_kj is not None else 999)):
    dg = f"{p.dg_kj:.1f}" if p.dg_kj is not None else "—"
    stb = f"{p.stability:.3f}" if p.stability is not None else "—"
    print(f"  {p.formula:<12}{p.source_name:<14}{dg:>12}{stb:>11}")

dgs = [p.dg_kj for p in prods if p.dg_kj is not None]
check("所有 ΔG 在合理区间", all(DG_SANE_MIN <= d <= DG_SANE_MAX for d in dgs))
check("ΔG 有区分度", len(set(round(d, 1) for d in dgs)) > 1)
check("组内稳定性落在 [0,1]",
      all(0.0 <= p.stability <= 1.0 for p in prods if p.stability is not None))

print()
print("  ── 反面验证：不可靠的反应类型确实被跳过 ──")
r_ester = rule_by_id["hydrolysis_ester_001"]
ester_subs = [
    Compound(smiles="COC(=O)c1ccccc1", name="苯甲酸甲酯", herb="测试"),
    Compound(smiles="CC(=O)OCC", name="乙酸乙酯", herb="测试"),
    Compound(smiles="COC(=O)CCCCC", name="己酸甲酯", herb="测试"),
]
ester_prods = []
for s in ester_subs:
    ester_prods.extend(engine.apply_rule(r_ester, s, activation=0.8, round_no=1))
st_e = assign_thermo(ester_prods, th, rule_by_id)
n_e = sum(1 for p in ester_prods if p.dg_kj is not None)
print(f"  酯水解产物 {len(ester_prods)} 个，拿到 ΔG 的 {n_e} 个，"
      f"skipped_unreliable={st_e.get('skipped_unreliable')}")
check("★水解类被跳过（气相 ΔG 符号系统性错误）★", n_e == 0)
check("测试里的规则确实带了 thermo_unreliable 标记",
      rule_by_id["hydrolysis_ester_001"].get("thermo_unreliable") is True)
check("环氧化物开环【不】被跳过（实测 ΔG 符号正确）",
      not rule_by_id["hydrolysis_epoxide_001"].get("thermo_unreliable"))

print()
print("=" * 88)
print("场景 B：中药大分子 —— 覆盖率不足，应当正确整体回退")
print("=" * 88)
seeds = compounds_of_herb("附子", limit=20)
sizes = []
for s in seeds:
    m = get_mol(s.smiles)
    if m:
        sizes.append(m.GetNumHeavyAtoms())
if sizes:
    over = sum(1 for n in sizes if n > MAX_HEAVY_FOR_XTB)
    print(f"  附子成分 {len(sizes)} 个，重原子数 范围 [{min(sizes)}, {max(sizes)}]")
    print(f"  超过 xTB 可靠上限（{MAX_HEAVY_FOR_XTB}）的: {over}/{len(sizes)}"
          f"  ({over/len(sizes):.0%})")
check("★附子成分大多超出 xTB 可靠范围★", over > len(sizes) * 0.5)

cond = T.get_template("酸水解")

t0 = time.time()
resA = cascade(engine, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40)
tA = time.time() - t0
realA = [p for p in resA.products if not p.is_byproduct]
print(f"\n  基线（纯启发式）：产物 {resA.total}，耗时 {tA:.1f}s")

t0 = time.time()
resB = cascade(engine, seeds, cond, max_rounds=2, min_new=5, frontier_limit=40,
               thermo=th, thermo_top_k=60)
tB = time.time() - t0
realB = [p for p in resB.products if not p.is_byproduct]
print(f"  接入 xTB      ：产物 {resB.total}，耗时 {tB:.1f}s")
print(f"  热力学统计     : {resB.thermo_stats}")

cov = resB.thermo_stats.get("coverage", 0.0)
reverted = resB.thermo_stats.get("reverted")
print(f"  覆盖率         : {cov:.0%}（阈值 {MIN_THERMO_COVERAGE:.0%}）")
if reverted:
    print(f"  回退原因       : {reverted}")

check("★覆盖率不足时正确整体回退★", bool(reverted))
check("★回退后没有留下半套 ΔG（不许混用尺度）★",
      all(p.dg_kj is None for p in resB.products))
check("回退后排序与启发式一致",
      [p.smiles for p in resA.products[:20]] == [p.smiles for p in resB.products[:20]])
check("回退后耗时没有爆炸（缓存生效）", tB < 120)

print()
print("  回退后的 Top5（应与基线一致）：")
for p in realB[:5]:
    print(f"    {p.score:.3f}  {p.formula:<12}{p.rule_name:<10}← {p.source_name[:20]}")

BEN = canon("OC(=O)c1ccccc1")
def rank_of(res, smi):
    for i, p in enumerate([x for x in res.products if not x.is_byproduct], 1):
        if canon(p.smiles) == smi:
            return i
    return None

ra, rb = rank_of(resA, BEN), rank_of(resB, BEN)
print(f"\n  苯甲酸排名：基线 第 {ra} 名 / xTB 版 第 {rb} 名")
check("两种模式下苯甲酸都在", ra is not None and rb is not None)

print()
print("=" * 88)
print("纪律复核")
print("=" * 88)
uc = Path(r"D:\TCMAI\data\xtb_cache")
n_user = len(list(uc.glob("*.json"))) if uc.exists() else 0
print(f"  D:\\TCMAI\\data\\xtb_cache : {n_user} 个（应仍为 7）")
print(f"  暂存区缓存             : {len(list(th.cache_dir.glob('*.json')))} 个")
print(f"  Thermo 计数            : {th.stats.summary()}")
check("★用户项目未被写入★", n_user <= 7)

print()
print("=" * 88)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 88)
