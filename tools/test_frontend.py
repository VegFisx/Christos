# -*- coding: utf-8 -*-
"""前端入口回归测试：三种输入方式 + 追溯完整性 + 条件切换。"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from predict import predict, parse_formula_text
import templates as T

PASS, FAIL = [], []


def check(n, c):
    (PASS if c else FAIL).append(n)
    print(f"  {'✓' if c else '✗'} {n}")


print("=" * 88)
print("① 方剂原文解析（应复用项目里的 src/parse_peifang.py）")
print("=" * 88)
TEXT = "甘草2两（炙），干姜1两半，附子1枚（生用，去皮，破8片）。"
parsed = parse_formula_text(TEXT)
print(f"  原文: {TEXT}")
for p in parsed:
    print(f"    {p['herb']:<8} 剂量={p.get('dose')}  炮制={p.get('process')}")
check("解析出 3 味药", len(parsed) == 3)
check("药名正确", [p["herb"] for p in parsed] == ["甘草", "干姜", "附子"])
check("★复用了项目里的解析器★",
      any("parse_peifang" in str(p.get("_parser", "")) for p in parsed))
check("剂量被识别", all(p.get("dose") for p in parsed))

print()
print("=" * 88)
print("② 单味药 → 完整产物清单")
print("=" * 88)
r1 = predict(herbs=["甘草"], max_per_herb=15, frontier_limit=30,
             max_rounds=8, min_new=10)
print(f"  成分 {len(r1.compounds)} | 激活规则 {len(r1.active_rules)}/{r1.n_rules}")
print(f"  跑了 {r1.cascade.rounds} 轮，收敛={r1.cascade.converged}")
print(f"  产物 {r1.cascade.total}（主体 {len(r1.main_products())}）")
print(f"  按分子式归并后 {len(r1.diverse_products())} 个")
check("取到成分", len(r1.compounds) > 0)
check("有激活规则", len(r1.active_rules) > 10)
check("★级联收敛★", r1.cascade.converged)
check("有产物", len(r1.main_products()) > 0)
check("归并后数量少于原始", len(r1.diverse_products()) < len(r1.main_products()))

print()
print("  Top 5（归并后）：")
for p, n_iso in r1.diverse_products(top=5):
    print(f"    {p.score:.3f}  {p.formula:<12}{p.rule_name:<14}"
          f"← {p.source_name[:22]}  (异构体 {n_iso})")

print()
print("=" * 88)
print("③ 来源追溯完整性")
print("=" * 88)
sample = r1.main_products(1)[0]
print(f"  产物 SMILES : {sample.smiles[:64]}")
print(f"  分子式/分子量: {sample.formula} / {sample.mw}")
print(f"  由哪条规则   : {sample.rule_name} ({sample.rule_id})")
print(f"  来自哪个成分 : {sample.source_name}")
print(f"  成分 SMILES  : {sample.source_smiles[:50]}")
print(f"  来自哪味药   : {sample.source_herb}")
print(f"  第几轮       : {sample.round}")
print(f"  置信度       : {sample.score}")
check("★追溯六要素齐全★",
      all([sample.smiles, sample.formula, sample.rule_id,
           sample.source_name, sample.source_herb, sample.round >= 1]))
check("有置信度分数", 0 < sample.score <= 1)

print()
print("  ── 按药材/规则/轮次聚合 ──")
print(f"    按药材: {dict(r1.by_herb())}")
print(f"    按轮次: {dict(sorted(r1.by_round().items()))}")
print(f"    按规则 Top3: {r1.by_rule().most_common(3)}")
check("能按药材聚合", len(r1.by_herb()) >= 1)
check("能按规则聚合", len(r1.by_rule()) > 3)
check("能按轮次聚合", len(r1.by_round()) >= 1)

print()
print("=" * 88)
print("④ SMILES 直接输入")
print("=" * 88)
r2 = predict(smiles=["COC(=O)c1ccccc1", "OCCCC(=O)O"], condition="酸水解",
             max_rounds=3, frontier_limit=20)
print(f"  输入 2 个 SMILES → 成分 {len(r2.compounds)}")
for p, n in r2.diverse_products(top=6):
    print(f"    {p.score:.3f}  {p.formula:<12}{p.rule_name:<14}← {p.source_name}")
check("SMILES 输入被接受", len(r2.compounds) == 2)
check("有产物", len(r2.main_products()) > 0)

print()
print("=" * 88)
print("⑤ 条件切换真的改变结果")
print("=" * 88)
res = {}
for label in ("煎煮", "醇提", "无氧煎煮"):
    res[label] = predict(herbs=["甘草"], condition=label, max_per_herb=12,
                         frontier_limit=25, max_rounds=8, min_new=10)
    print(f"  {label:<6} 产物 {res[label].cascade.total:>5}  "
          f"收敛={res[label].cascade.converged}")
sets = {k: {p.smiles for p in v.main_products()} for k, v in res.items()}
print(f"  煎煮独有（无氧没有）: {len(sets['煎煮'] - sets['无氧煎煮'])} 个")
print(f"  醇提与煎煮产物差异  : {len(sets['醇提'] ^ sets['煎煮'])} 个")
check("★气氛改变产物集合★", len(sets["煎煮"] - sets["无氧煎煮"]) > 0)

print()
print("=" * 88)
print("⑥ JSON 导出")
print("=" * 88)
j = r1.to_json()
print(f"  顶层键: {sorted(j.keys())}")
print(f"  产物条数: {len(j['products'])}")
Path(STAGE / "reports" / "demo_output.json").write_text(
    json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
check("JSON 含产品列表", len(j["products"]) > 0)
check("JSON 含级联统计", "cascade" in j and "rounds" in j["cascade"])
check("JSON 可序列化", True)
check("产物条目带追溯字段",
      {"smiles", "rule_id", "source_name", "source_herb", "round", "score"}
      <= set(j["products"][0]))

print()
print("=" * 88)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 88)
