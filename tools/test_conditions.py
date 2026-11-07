# -*- coding: utf-8 -*-
"""条件层验证：证明"换个煎法，产物清单就变了"。

这个测试要回答的核心问题：
  在条件层之前，24 条规则无条件全开，煎煮和醇提跑出来一模一样。
  加了条件层之后，不同条件真的会激活不同的规则吗？
"""
import sys
from pathlib import Path

# Windows 控制台是 GBK：脚本自己打印 ✓/✗/中文，必须自己重设编码，别指望调用方设 PYTHONIOENCODING
# （AGENTS.md 第七节；本脚本 2026-10-11 实测在普通控制台直接 UnicodeEncodeError）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "conditions"))
sys.path.insert(0, str(STAGE / "rules"))

from model import Conditions
import templates as T
from activator import (activation_score, active_rules, explain,
                       solvent_matches, solvent_score, ph_score,
                       window_score, load_default_rules)
from schema import resolve_conditions

profiles, rules = load_default_rules()
print(f"规则库: {len(rules)} 条规则, {len(profiles)} 个条件窗口模板\n")

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name}")


print("=" * 84)
print("0. 基础：条件对象自检")
print("=" * 84)
c = T.get_template("煎煮")
check("煎煮模板自检通过", c.validate() == [])
check("稀有气体气氛可构造", all(
    Conditions(atmosphere=x).validate() == [] for x in ("He", "Ne", "Ar")))
bad = Conditions(temperature=999, pH=20, solvent="汽油")
probs = bad.validate()
check(f"非法条件被检出（{len(probs)} 个问题）", len(probs) >= 3)
for p in probs:
    print(f"      · {p}")
check("solvent_matches: ethanol 命中 alcohol 族",
      solvent_matches("ethanol", ["water", "alcohol"]))
check("solvent_matches: ethanol 不命中 water",
      not solvent_matches("ethanol", ["water", "aqueous"]))
check("window_score: 窗口内 = 1.0", window_score(100, {"min": 20, "max": 150}) == 1.0)
check("window_score: 轻微越界衰减", 0 < window_score(160, {"min": 20, "max": 150}) < 1.0)
check("window_score: 远越界 = 0", window_score(400, {"min": 20, "max": 150}) == 0.0)
check("solvent_score: 首选溶剂 = 1.0",
      solvent_score("water", ["water", "aqueous", "alcohol"]) == 1.0)
check("solvent_score: 次选溶剂衰减",
      solvent_score("ethanol", ["water", "aqueous", "alcohol"]) < 1.0)
check("solvent_score: 不在列表 = 0",
      solvent_score("oil", ["water", "aqueous", "alcohol"]) == 0.0)
check("ph_score: acid_base 在中性最低",
      ph_score(7.0, "acid_base") < ph_score(1.5, "acid_base"))
check("ph_score: neutral 在两极最低",
      ph_score(7.0, "neutral") > ph_score(1.5, "neutral"))

print()
print("=" * 84)
print("1. ★ 无氧煎煮：氧化反应必须全部熄灭")
print("=" * 84)
air = T.get_template("煎煮")
n2 = T.get_template("无氧煎煮")
act_air = {r["id"] for r, _, _ in active_rules(rules, profiles, air)}
act_n2 = {r["id"] for r, _, _ in active_rules(rules, profiles, n2)}
ox = {r["id"] for r in rules
      if r["category"] == "oxidation" and r.get("status") != "disabled"}

print(f"  煎煮(空气)  激活 {len(act_air)} 条")
print(f"  无氧煎煮(N2) 激活 {len(act_n2)} 条")
print(f"  氧化类【启用中】规则共 {len(ox)} 条："
      f"{sorted(r['name'] for r in rules if r['category'] == 'oxidation')}")
check("空气下氧化规则全部激活", ox <= act_air)
check("★氮气下氧化规则全部熄灭★", not (ox & act_n2))
print(f"  熄灭的氧化规则: {sorted(r['name'] for r in rules if r['id'] in (ox - act_n2))}")

print()
print("=" * 84)
print("2. ★ 还原气氛：还原反应只在通氢时发生")
print("=" * 84)
red = {r["id"] for r in rules
       if r["category"] == "reduction" and r.get("status") != "disabled"}
h2 = T.get_template("还原")
act_h2 = {r["id"] for r, _, _ in active_rules(rules, profiles, h2)}
print(f"  还原类【启用中】规则共 {len(red)} 条："
      f"{sorted(r['name'] for r in rules if r['category'] == 'reduction')}")
check("通氢时还原规则激活", red <= act_h2)
check("★煎煮(空气)下还原规则全部不激活★", not (red & act_air))
for inert_atm in ("He", "Ne", "Ar"):
    inert = Conditions(solvent=air.solvent, temperature=air.temperature,
                       time_min=air.time_min, pH=air.pH,
                       catalyst=air.catalyst, atmosphere=inert_atm)
    act_inert = {r["id"] for r, _, _ in active_rules(rules, profiles, inert)}
    check(f"★{inert_atm} 下氧化/还原规则全部熄灭★", not ((ox | red) & act_inert))

print()
print("=" * 84)
print("3. ★ 煎煮 vs 醇提：溶剂真的改变了结果")
print("=" * 84)
alc = T.get_template("醇提")
act_alc = {r["id"] for r, _, _ in active_rules(rules, profiles, alc)}
print(f"  煎煮(水 100°C)  激活 {len(act_air)} 条")
print(f"  醇提(乙醇 78°C) 激活 {len(act_alc)} 条")
check("醇提没有把水解类规则全部判死（溶剂归族生效）",
      len(act_alc) >= len(act_air) - 3)

# 逐条比分数
print(f"\n  {'规则':<20}{'煎煮':>9}{'醇提':>9}{'酸水解':>9}{'差异':>8}")
print("  " + "-" * 58)
acid = T.get_template("酸水解")
diffs = 0
for r in rules:
    if r.get("status") == "disabled":
        continue
    res, _ = resolve_conditions(r, profiles)
    s_air, _ = activation_score(r, res, air)
    s_alc, _ = activation_score(r, res, alc)
    s_ac, _ = activation_score(r, res, acid)
    mark = ""
    if abs(s_air - s_alc) > 1e-9:
        diffs += 1
        mark = "★"
    print(f"  {r['name']:<20}{s_air:>9.3f}{s_alc:>9.3f}{s_ac:>9.3f}{mark:>8}")
check(f"煎煮 vs 醇提 至少有规则分数不同（{diffs} 条）", diffs > 0)

print()
print("=" * 84)
print("4. 酸碱水解：pH 主导")
print("=" * 84)
base = T.get_template("碱水解")
res_ester, _ = resolve_conditions(next(r for r in rules if r["id"] == "hydrolysis_ester_001"), profiles)
s_neutral, _ = activation_score(next(r for r in rules if r["id"] == "hydrolysis_ester_001"), res_ester, air)
s_acid, _ = activation_score(next(r for r in rules if r["id"] == "hydrolysis_ester_001"), res_ester, acid)
print(f"  酯水解 在煎煮(pH 6.5)  分数 {s_neutral:.3f}")
print(f"  酯水解 在酸水解(pH 1.5) 分数 {s_acid:.3f}")
check("酯水解在酸水解条件下被激活", s_acid > 0)

print()
print("=" * 84)
print("5. 温度效应：室温浸泡 vs 煎煮")
print("=" * 84)
room = T.get_template("室温浸泡")
act_room = {r["id"] for r, _, _ in active_rules(rules, profiles, room)}
print(f"  室温浸泡(25°C) 激活 {len(act_room)} 条")
print(f"  煎煮(100°C)   激活 {len(act_air)} 条")
check("煎煮激活的规则不少于室温浸泡", len(act_air) >= len(act_room))

print()
print("=" * 84)
print("6. 实际输出样例：煎煮")
print("=" * 84)
print(explain(rules, profiles, air))

print()
print("=" * 84)
print("7. 实际输出样例：无氧煎煮")
print("=" * 84)
print(explain(rules, profiles, n2))

print()
print("=" * 84)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
if FAIL:
    for f in FAIL:
        print(f"  ✗ {f}")
print("=" * 84)
