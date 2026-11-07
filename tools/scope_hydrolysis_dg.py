# -*- coding: utf-8 -*-
r"""看清「气相 ΔG 对哪类反应不可靠」的真实边界。

上轮测到：
    乙酸乙酯水解  +13.2  （化学应为 ≈ -4）  ✗ 符号错
    苯甲酸甲酯水解 +16.5  （应为负）        ✗
    葡萄糖苷水解   +11.0  （应为负）        ✗
    乙醇脱水      +69.3  （应为正）        ✓
    乙烯水合      -69.3  （应为负）        ✓ ← 注意：这条【也涉及水】！
    丙酮加氢      -52.1  （应为负）        ✓

★ 所以不是「凡涉及水就不可靠」★
    水合（C=C + H2O → C-C-OH，水被【加上去】）→ 气相 ΔG 是准的
    水解（R-O-R' + H2O → R-OH + R'-OH，水【切断】一根键）→ 气相 ΔG 是错的

  区别在于：水解的驱动力来自【溶剂化熵】，气相算不出来。

本脚本把范围量清楚：哪些规则属于"水解类"，它们的 ΔG 符号是否系统性为正。
"""
import json
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, r"D:\TCMAI\src")
sys.path.insert(0, str(STAGE / "libs"))
for d in ("core",):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from thermo import Thermo

RULES = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]

print("=" * 96)
print("① 规则分类：哪些是「水解」（水切断一根键）")
print("=" * 96)
HYDROLYSIS_HINT = ("水解", "hydrolysis")
rows = []
for r in RULES:
    if r.get("status") == "disabled":
        continue
    name = r["name"]
    rid = r["id"]
    smarts = r.get("smarts", "")
    co = r.get("co_reagents") or {}
    by = r.get("byproducts") or {}
    # 判断依据：规则名含"水解"，或 SMARTS 产物侧出现 [OH2]（水）
    is_hyd = any(h in rid.lower() for h in HYDROLYSIS_HINT) or any(h in name for h in ("水解",))
    water_out = "OH2" in smarts or "O]" in smarts.split(">>")[-1][:0]
    water_as_product = "[OH2]" in smarts
    rows.append((rid, name, is_hyd, co, by, water_as_product))

hyd = [r for r in rows if r[2]]
nonhyd = [r for r in rows if not r[2]]
print(f"  启用规则 {len(rows)} 条")
print(f"  判为「水解」 {len(hyd)} 条：")
for rid, name, _h, co, by, w in hyd:
    print(f"      {name:<20} co={co}  by={by}")
print(f"  其余 {len(nonhyd)} 条非水解")

print()
print("=" * 96)
print("② 实测：水解类 vs 非水解类的 ΔG 符号")
print("=" * 96)
th = Thermo(n_conf=2)
print(f"  Thermo 可用: {th.available}")

CASES = [
    # (标签, 左侧, 右侧, 化学预期符号)
    ("水解·乙酸乙酯",   ["CC(=O)OCC", "O"], ["CC(=O)O", "CCO"], -1),
    ("水解·苯甲酸甲酯", ["COC(=O)c1ccccc1", "O"], ["OC(=O)c1ccccc1", "CO"], -1),
    ("水解·葡萄糖苷",   ["COC1OC(CO)C(O)C(O)C1O", "O"],
                        ["OC1OC(CO)C(O)C(O)C1O", "CO"], -1),
    ("水解·乙酰胺",     ["CC(=O)N", "O"], ["CC(=O)O", "N"], -1),
    ("水合·乙烯",       ["C=C", "O"], ["CCO"], -1),
    ("水合·丙酮",       ["CC(C)=O", "O"], ["CC(C)(O)O"], -1),
    ("脱水·乙醇",       ["CCO"], ["C=C", "O"], +1),
    ("加氢·丙酮",       ["CC(C)=O", "[H][H]"], ["CC(C)O"], -1),
    ("氧化·乙醇",       ["CCO", "O"], ["CC=O", "O"], -1),
]

print(f"\n  {'反应':<20}{'ΔG':>9}{'预期':>7}{'判定':>6}")
print("  " + "-" * 46)
hyd_wrong = 0
hyd_total = 0
nonhyd_wrong = 0
nonhyd_total = 0
for label, left, right, expect in CASES:
    dg = th.reaction_dg(left, right)
    if dg is None:
        print(f"  {label:<20}{'失败':>9}{'':>7}{'—':>6}")
        continue
    ok = (dg < 0) if expect < 0 else (dg > 0)
    is_hyd = label.startswith("水解")
    if is_hyd:
        hyd_total += 1
        hyd_wrong += (not ok)
    else:
        nonhyd_total += 1
        nonhyd_wrong += (not ok)
    print(f"  {label:<20}{dg:>9.1f}{'负' if expect < 0 else '正':>7}"
          f"{'✓' if ok else '✗ 错':>6}")

print()
print("=" * 96)
print("③ 结论")
print("=" * 96)
print(f"  水解类：{hyd_total} 个样本，符号错 {hyd_wrong} 个")
print(f"  非水解：{nonhyd_total} 个样本，符号错 {nonhyd_wrong} 个")
print()
print("  ★ 若水解【全错】而非水解【基本不错】，说明边界就是「水解」这一类 ★")
print()
print("  → 处置建议：让 assign_thermo 跳过水解类规则，")
print("     不让一个已知系统性错误的信号去影响排序。")
