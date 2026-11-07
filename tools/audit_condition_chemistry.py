# -*- coding: utf-8 -*-
r"""
审计条件激活层的【化学合理性】
================================

目标里明确点名要实现这 8 种工艺：
    煎煮 / 水提 / 醇提 / 酸水解 / 碱水解 / 氧化 / 还原 / 酶催化

前面我只验证过"不同工艺产出不同分子"，**没验证过"激活的规则对不对"**。

本脚本做三件事：
  ① 把每条规则的 condition_profile 摊开看
  ② 对 8 种工艺，列出各自激活了哪些规则
  ③ 用化学常识去卡：
       · 酸水解  应当激活水解类，不该激活还原类
       · 还原    应当激活还原类，不该激活氧化类
       · 氧化    应当激活氧化类
       · 醇提    应当激活酯交换/酯化（乙醇参与）
       · 无氧    应当关掉氧化类
       · 酶催化  应当是窄的、专一的子集
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

import templates as T
from activator import active_rules

RULES = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))["rules"]
PROFILES = json.loads((STAGE / "conditions" / "profiles.json").read_text(encoding="utf-8")) \
    if (STAGE / "conditions" / "profiles.json").exists() else {}

print("=" * 100)
print("① 每条规则的 condition_profile（类别名）")
print("=" * 100)
print(f"  {'规则':<22}{'类别':<16}{'profile':<12}{'优先级':>7}{'可逆'}")
print("  " + "-" * 70)
for r in RULES:
    if r.get("status") == "disabled":
        continue
    prof = r.get("condition_profile")
    print(f"  {r['name']:<22}{r.get('category',''):<16}{str(prof):<12}"
          f"{r.get('priority', 0):>7.2f}   {'是' if r.get('reversible') else ''}")

print()
print("=" * 100)
print("② 8 种工艺各激活了哪些规则")
print("=" * 100)

TEMPLATE_NAMES = ["煎煮", "水提", "醇提", "酸水解", "碱水解", "氧化", "还原", "酶催化"]
profiles_obj = None
try:
    from engine import load_engine
    _e, _r, profiles_obj = load_engine()
except Exception as ex:
    print(f"  load_engine 失败: {ex}")

per_cond = {}
for name in TEMPLATE_NAMES:
    try:
        cond = T.get_template(name)
    except Exception as ex:
        print(f"  ✗ 模板 {name} 取不到: {ex}")
        continue
    act = active_rules(RULES, profiles_obj, cond, 0.15)
    ids = [r["id"] for r, _s, _w in act]
    per_cond[name] = ids
    cats = Counter(r.get("category", "?") for r in RULES if r["id"] in ids)
    print(f"\n  【{name}】激活 {len(ids)}/58 条")
    print(f"      按类别: {dict(cats.most_common())}")

print()
print("=" * 100)
print("③ 化学常识核查")
print("=" * 100)

def has(cond, cat_prefix):
    return [i for i in per_cond.get(cond, []) if i.startswith(cat_prefix)]

def n(cond, cat_prefix):
    return len(has(cond, cat_prefix))

CHECKS = [
    ("酸水解 应激活水解类",        lambda: n("酸水解", "hydrolysis") >= 5),
    ("酸水解 不应激活还原类",      lambda: n("酸水解", "reduction") == 0),
    ("还原   应激活还原类",        lambda: n("还原", "reduction") >= 3),
    ("还原   不应激活氧化类",      lambda: n("还原", "oxidation") == 0),
    ("氧化   应激活氧化类",        lambda: n("氧化", "oxidation") >= 5),
    ("氧化   应激活羟基化",        lambda: n("氧化", "hydroxyl") >= 1),
    ("无氧煎煮 不应激活氧化类",    lambda: n("无氧煎煮", "oxidation") == 0),
    ("醇提   应激活酯化/酯交换",   lambda: (n("醇提", "esterification") +
                                            n("醇提", "condensation")) >= 1),
    ("酶催化 应是窄子集",          lambda: 0 < len(per_cond.get("酶催化", [])) <= 12),
    ("煎煮   应激活水解类",        lambda: n("煎煮", "hydrolysis") >= 4),
    ("水提   应激活水解类",        lambda: n("水提", "hydrolysis") >= 4),
    ("碱水解 应激活水解类",        lambda: n("碱水解", "hydrolysis") >= 4),
]
PASS, FAIL = [], []
for label, fn in CHECKS:
    try:
        ok = bool(fn())
    except Exception as ex:
        ok = False
        label += f"  ({type(ex).__name__})"
    (PASS if ok else FAIL).append(label)
    print(f"  {'✓' if ok else '✗'} {label}")

print()
print("=" * 100)
print("④ 可疑项：规则类别 与 激活工艺 不搭的")
print("=" * 100)
SUSPECT = {
    "reduction":    {"酸水解", "氧化", "无氧煎煮"},
    "oxidation":    {"还原", "无氧煎煮"},
    "hydrolysis":   {"醇提"},
    "esterification": {"酸水解"},
}
found = False
for r in RULES:
    if r.get("status") == "disabled":
        continue
    cat = r.get("category", "")
    bad = SUSPECT.get(cat)
    if not bad:
        continue
    for cname in bad:
        if r["id"] in per_cond.get(cname, []):
            print(f"  ★ {r['name']}（{cat}）在【{cname}】下被激活")
            found = True
if not found:
    print("  （未发现明显不搭的组合）")

print()
print("=" * 100)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 100)
