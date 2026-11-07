# -*- coding: utf-8 -*-
r"""
系统审计：所有 co_substrate_pool 里的陪跑试剂，在煎煮里说得通吗？
==================================================================

已确认的问题：酰胺化(分子间) 的陪跑试剂里有【甲胺(CN)】和【氨(N)】，
when_solvent=None（永远可用）→ 煎煮水里凭空生成 N-甲基酰胺。

这是「陪跑试剂不合理」这类 bug 的第一个实例。
本脚本把全部规则的 co_substrate_pool 摊开，逐个判断。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "core"))
import sys as _s
for d in ("conditions", "rules", "libs"):
    p = STAGE / d
    if p.is_dir():
        _s.path.insert(0, str(p))

RULES = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

# 煎煮/水提里真实存在的分子（判据：药材自身成分 + 水 + 常见小分子）
PLAUSIBLE_IN_WATER = {
    "O":        "水",
    "CCO":      "乙醇（醇提才有）",
    "CO":       "甲醇（醇提才有）",
    "NCC(=O)O": "甘氨酸（药材游离氨基酸）",
}
# 明确【不】可能凭空出现的
IMPLAUSIBLE = {
    "N":  "氨（煎煮水里没有）",
    "CN": "甲胺（煎煮水里没有）",
    "C":  "甲烷",
    "CC": "乙烷",
    "O=O": "氧气（无氧工艺下没有）",
}

print("=" * 100)
print("所有规则的 co_substrate_pool")
print("=" * 100)
allpools = []
for r in RULES:
    if r.get("status") == "disabled":
        continue
    pool = r.get("co_substrate_pool") or []
    if not pool:
        continue
    allpools.append((r, pool))

print(f"  带 co_substrate_pool 的规则: {len(allpools)} 条\n")
for r, pool in allpools:
    print(f"  【{r['name']}】{r['id']}")
    for it in pool:
        smi = it.get("smiles")
        when = it.get("when_solvent")
        tag = ""
        if smi in IMPLAUSIBLE:
            tag = f"  ★★ 不合理：{IMPLAUSIBLE[smi]}"
        elif smi in PLAUSIBLE_IN_WATER:
            tag = f"  （{PLAUSIBLE_IN_WATER[smi]}）"
        if when is None:
            tag += "   [when_solvent=None → 任何工艺都可用]"
        print(f"      {str(smi):<22}when={str(when):<44}{tag}")
    print()

print("=" * 100)
print("判定")
print("=" * 100)
bad = []
for r, pool in allpools:
    for it in pool:
        smi = it.get("smiles")
        when = it.get("when_solvent")
        if smi in IMPLAUSIBLE and when is None:
            bad.append((r["name"], smi, IMPLAUSIBLE[smi]))

if bad:
    print(f"  ★ 发现 {len(bad)} 处「不可能存在却永远可用」的陪跑试剂：")
    for nm, smi, why in bad:
        print(f"      {nm:<22}{smi:<8}{why}")
    print()
    print("  后果：这些反应会在【所有工艺】下发生，凭空造出产物。")
else:
    print("  ✓ 未发现")

print()
print("=" * 100)
print("顺带：哪些陪跑试剂【有】when_solvent 约束（正确的做法）")
print("=" * 100)
ok = []
for r, pool in allpools:
    for it in pool:
        if it.get("when_solvent") is not None:
            ok.append((r["name"], it.get("smiles"), it.get("when_solvent")))
print(f"  有约束的 {len(ok)} 条：")
for nm, smi, when in ok:
    print(f"      {nm:<22}{str(smi):<12}{when}")

print()
print("=" * 100)
print(f"结果：{len(bad)} 处不合理 / 共 {len(allpools)} 条规则带陪跑试剂池")
if bad:
    for nm, smi, why in bad:
        print(f"  ✗ {nm} 里的 {smi}：{why}")
else:
    print("  ✓ 全部陪跑试剂都在该工艺下说得通")
print("=" * 100)

# ★ 作为防线，发现问题必须返回非零 ★
raise SystemExit(1 if bad else 0)
