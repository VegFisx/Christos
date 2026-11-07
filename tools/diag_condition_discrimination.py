# -*- coding: utf-8 -*-
r"""
诊断：条件激活层到底有没有区分「煎煮/水提/醇提/酸水解/碱水解」？

上面的审计发现：这五种工艺【激活的规则集合完全相同】（都是 43/58）。
只有氧化(12)和还原(6)因为气氛硬门槛被区分开。

那么工艺差异从哪来？两种可能：
  H1  来自【激活分数】—— 规则集合相同，但强度不同，级联门槛把弱的筛掉
  H2  根本没有区分 —— 差异只是产物生成的随机性（已排除）或别的

本脚本把关键规则的激活分数在 8 种工艺下摊开，看有没有真实区分。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

import templates as T
from activator import activation_score, active_rules
from engine import load_engine

RULES = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
ENG, _, PROFILES = load_engine()

CONDS = ["煎煮", "水提", "醇提", "酸水解", "碱水解", "氧化", "还原", "酶催化"]

# 挑有代表性的规则
KEYS = [
    ("酯水解", "hydrolysis_ester_001"),
    ("糖苷水解", "hydrolysis_glycoside_001"),
    ("酯交换", None),
    ("酯化(分子间)", "esterification_intermolecular_001"),
    ("γ-内酯化", None),
    ("脱水", None),
    ("羟基氧化", None),
    ("酮还原", None),
    ("美拉德简化", None),
]
by_id = {r["id"]: r for r in RULES}
by_name = {r["name"]: r for r in RULES}

# 补全 None 的 id
for i, (nm, rid) in enumerate(KEYS):
    if rid is None and nm in by_name:
        KEYS[i] = (nm, by_name[nm]["id"])

print("=" * 104)
print("激活分数矩阵（0 = 该工艺下不可能发生）")
print("=" * 104)
hdr = f"  {'规则':<16}" + "".join(f"{c:>10}" for c in CONDS)
print(hdr)
print("  " + "-" * (len(hdr) - 2))

resolved_cache = {}
from schema import resolve_conditions

rows = []
for nm, rid in KEYS:
    r = by_id.get(rid)
    if r is None:
        print(f"  {nm:<16} (规则不存在)")
        continue
    if rid not in resolved_cache:
        resolved, _ = resolve_conditions(r, PROFILES)
        resolved_cache[rid] = resolved
    resolved = resolved_cache[rid]
    cells = []
    for c in CONDS:
        run = T.get_template(c)
        s, reasons = activation_score(r, resolved, run)
        cells.append(s)
    rows.append((nm, cells))
    line = f"  {nm:<16}" + "".join(f"{s:>10.3f}" for s in cells)
    print(line)

print()
print("=" * 104)
print("判定：每种工艺的『分数指纹』是否互不相同")
print("=" * 104)
# ★ 上一版这里写错了 ★
#   我用「在全部 8 种工艺下都非零的规则」当样本，结果那个集合是【空集】
#   （因为氧化/还原有气氛硬门槛，必然有 0）→ 空集比较恒真 →
#   打印出「所有规则对这 5 种工艺完全无感」这个【与事实相反】的结论。
#   现在改成：对每条【启用】规则，数它在 5 种工艺下有几种不同分数。

SUB = [0, 1, 2, 3, 4]      # 煎煮/水提/醇提/酸水解/碱水解
SUB_NAMES = [CONDS[i] for i in SUB]

rows = []
for r in RULES:
    if r.get("status") == "disabled":
        continue
    resolved, _ = resolve_conditions(r, PROFILES)
    sc = [activation_score(r, resolved, T.get_template(c))[0] for c in CONDS]
    sub = [sc[i] for i in SUB]
    rows.append((r["name"], r["category"], sc, sub))

print(f"  启用规则 {len(rows)} 条")
print()
print(f"  {'规则':<22}{'类别':<16}{'5工艺下不同分数个数':>20}   判定")
print("  " + "-" * 74)
n_indiff = 0
for nm, cat, sc, sub in sorted(rows, key=lambda x: len(set(round(v, 6) for v in x[3]))):
    k = len(set(round(v, 6) for v in sub))
    if k == 1:
        n_indiff += 1
        tag = "★对这 5 种工艺完全无感★" if all(v > 0 for v in sub) else "(含 0，正常)"
    elif k == 2:
        tag = "只分 2 档"
    else:
        tag = f"分 {k} 档"
    print(f"  {nm:<22}{cat:<16}{k:>20}   {tag}")

print()
k_vals = [len(set(round(v, 6) for v in r[3])) for r in rows]
print(f"  不同分数个数的分布: "
      f"{ {k: k_vals.count(k) for k in sorted(set(k_vals))} }")
print(f"  对 5 种工艺完全无感（含全为 0 的）: {n_indiff}/{len(rows)}")
n_indiff_nonzero = sum(1 for r in rows
                       if len(set(round(v, 6) for v in r[3])) == 1
                       and all(v > 0 for v in r[3]))
print(f"  其中【非零且完全无感】的: {n_indiff_nonzero} 条")

print()
print("=" * 104)
print("结论")
print("=" * 104)
if n_indiff_nonzero > len(rows) * 0.5:
    print(f"""
  ★ 多数常激活规则（{n_indiff_nonzero}/{len(rows)}）对这 5 种工艺无感 ★
""")
else:
    print(f"""
  ✓ 激活层【确实在区分】这 5 种工艺：
    只有 {n_indiff_nonzero}/{len(rows)} 条非零规则对它们完全无感，
    多数规则给出了不同的分数。
""")
print("""  但要看清区分的【强度】：
     · 差异只有 10~20% 的，实际区分力很弱
     · 差异需要大到能跨过传播门槛（0.35）才真正改变产物
""")

