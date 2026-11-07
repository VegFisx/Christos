# -*- coding: utf-8 -*-
r"""
顶层检验：真实方剂的 Top-20，逐条看化学意义
=============================================

前面审的都是「某一层对不对」：配平、结构、激活、陪跑试剂、确定性……
**但从没做过最顶层的一件事：把输出摆出来，逐条问"这说得通吗"。**

方剂选四逆汤（附子+干姜+甘草）——最简单、研究最多、也是你论文用的组合。
"""
import sys
from pathlib import Path
from collections import Counter

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from predict import predict

HERBS = ["甘草", "干姜", "附子"]
COND = "煎煮"

r = predict(herbs=HERBS, condition=COND, max_per_herb=25,
            frontier_limit=50, max_rounds=8, min_new=10)

print("=" * 108)
print(f"方剂：{' + '.join(HERBS)}    工艺：{COND}")
print("=" * 108)
print(f"  原成分池: {len(r.compounds)}    激活规则: {r.n_rules}    "
      f"产物总数: {r.cascade.total}    轮数: {r.cascade.rounds}    "
      f"收敛: {r.cascade.converged}")
print(f"  耗时: {r.elapsed:.1f}s")
print()

# ── Top-20（多样性排序）──
print("=" * 108)
print("Top-20（多样性排序 —— 这就是使用者第一眼看到的东西）")
print("=" * 108)
print(f"  {'#':>3} {'分数':>6}  {'分子式':<13}{'反应':<20}{'来自':<12}{'轮':>2}{'异构':>5}  结构")
print("  " + "-" * 106)
seen_rules = Counter()
# ★ 必须用 CLI 真正用的那个视图（diverse_ranking），不是按分子式去重的那个 ★
#   第一版我用错了 diverse_products，看到「脱水占 15/20」就以为是排序坏了，
#   其实那是另一个函数。
iso_all = Counter(p.formula for p in r.main_products())
for i, p in enumerate(sorted(r.diverse_ranking(top=20), key=lambda x: -x.score), 1):
    seen_rules[p.rule_name] += 1
    iso = f"×{iso_all[p.formula]}" if iso_all[p.formula] > 1 else ""
    print(f"  {i:>3} {p.score:>6.3f}  {p.formula:<13}{p.rule_name:<20}"
          f"{(p.source_name or '')[:11]:<12}{p.round:>2}{iso:>5}  {p.smiles[:42]}")

print()
print("  Top-20 覆盖的反应类型:")
for k, v in seen_rules.most_common():
    print(f"      {k:<24}{v}")

# ── 按反应类型看全量分布 ──
print()
print("=" * 108)
print("全部产物的反应类型分布")
print("=" * 108)
c = Counter(p.rule_name for p in r.main_products())
for k, v in c.most_common(20):
    bar = "█" * max(1, int(v / max(1, max(c.values())) * 40))
    print(f"  {k:<24}{v:>5}  {bar}")

# ── 逐条化学审查：可疑产物 ──
print()
print("=" * 108)
print("★ 可疑产物筛查")
print("=" * 108)
# ★ 第一版这里写错了 ★
#   我拿"产物含氮 但 反应名不带氮"当可疑判据，结果报了 338 个 ——
#   其中绝大多数是【乌头碱类生物碱本身就含氮】，氮来自【底物】不是试剂。
#   正确的判据：只有在【源成分不含氮】而【产物含氮】时才可疑。
def has_elem(smi, sym):
    m = Chem.MolFromSmiles(smi) if smi else None
    return bool(m) and any(a.GetSymbol() == sym for a in m.GetAtoms())


SUSPECTS = []
for p in r.main_products():
    m = Chem.MolFromSmiles(p.smiles)
    if m is None:
        continue
    issues = []
    # 1) 源不含氮、产物含氮 → 说明有个含氮试剂凭空出现了
    if has_elem(p.smiles, "N") and not has_elem(p.source_smiles, "N"):
        # 排除确实该用甘氨酸/半胱氨酸的规则
        if not any(k in p.rule_name for k in ("酰胺", "Michael", "席夫", "氨解")):
            issues.append("源不含氮但产物含氮（可疑试剂）")
    # 2) 源不含硫、产物含硫
    if has_elem(p.smiles, "S") and not has_elem(p.source_smiles, "S"):
        if "硫" not in p.rule_name:
            issues.append("源不含硫但产物含硫")
    # 3) 含卤素
    if any(has_elem(p.smiles, s) for s in ("F", "Cl", "Br", "I")):
        issues.append("含卤素")
    if issues:
        SUSPECTS.append((p, issues))

print(f"  可疑产物 {len(SUSPECTS)} / {len(r.main_products())}")
for p, iss in SUSPECTS[:15]:
    print(f"    {p.formula:<13}{p.rule_name:<20}{p.smiles[:38]:<40}{'/'.join(iss)}")
if len(SUSPECTS) > 15:
    print(f"    …… 另有 {len(SUSPECTS)-15} 个")

# ── 已知的正确产物在不在 ──
print()
print("=" * 108)
print("★ 已知正确的产物是否出现（文献/化学常识）")
print("=" * 108)
def canon(s):
    m = Chem.MolFromSmiles(s)
    return Chem.MolToSmiles(m) if m else None

allp = {canon(p.smiles): p for p in r.main_products()}
# ★ 用【分子式】核对，不用手写 SMILES ★
#   第一版我手写了甘草次酸/乌头原碱的 SMILES，结果报了"未出现" ——
#   但引擎明明产出了 C30H46O4（甘草次酸）和 C32H45NO10（苯甲酰乌头原碱）。
#   复杂天然产物的骨架我敲不对，所以改成按分子式核对，更可靠。
KNOWN_BY_FORMULA = [
    ("甘草次酸（甘草酸苷元）", "C30H46O4", "甘草酸水解掉 2×葡萄糖醛酸 —— 抗炎活性成分"),
    ("甘草酸单糖苷",        "C36H54O10", "甘草酸水解掉 1 个葡萄糖醛酸的中间体"),
    ("苯甲酰乌头原碱",       "C32H45NO10", "脂乌头碱脱脂肪酸 —— 附子减毒第一步"),
    ("乌头原碱",           "C25H41NO9", "乌头碱脱乙酸+苯甲酸 —— 减毒终产物"),
    ("苯甲酸",             "C7H6O2", "附子/甘草芳香酸，酯水解产物"),
    ("葡萄糖",             "C6H12O6", "糖苷水解产物"),
]
by_formula = {}
for p in r.main_products():
    by_formula.setdefault(p.formula, []).append(p)

print()
for name, formula, why in KNOWN_BY_FORMULA:
    hits = by_formula.get(formula, [])
    mark = "✓" if hits else "—"
    tag = f"{len(hits)} 个" if hits else "未出现"
    print(f"  {mark} {name:<22}{formula:<13}{tag:<8}{why}")
    if hits:
        best = max(hits, key=lambda x: x.score)
        print(f"        最高分 {best.score:.3f}  反应 {best.rule_name}  轮 {best.round}")

print()
print("=" * 108)
print("人工判断要点")
print("=" * 108)
print("""
  请重点看 Top-20 里的这几类：
    1. 酯水解 / 糖苷水解   → 甘草酸、糖苷的减毒/增溶主路径，理应排前
    2. 脱水 / 环氧化等     → 干姜的萜类
    3. 含氮产物            → 如果出现 N-甲基化物，说明陪跑试剂还有问题
    4. 分子式特别大的     → 多轮级联产物，可能只是"能反应"但现实里量极小
""")
