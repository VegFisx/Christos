# -*- coding: utf-8 -*-
r"""
确定性审计：把整条链路每个环节都打乱输入跑两遍
================================================

★ 动机

  第 31 轮【偶然】发现级联不可复现（只打乱输入顺序，输出只有 22~36% 相同），
  根因是 `_sample_frontier` 按插入顺序取。

  一个地方有这种问题，别的地方也可能有。
  **不能靠偶然发现，要系统地查。**

★ 审计对象

  ① engine.step         单轮：底物池 × 激活规则
  ② cascade             多轮级联
  ③ scorer.diverse_...  多样性排序（取 Top-N）
  ④ api.predict         完整前端链路
  ⑤ active_rules        条件激活
  ⑥ classify_product    产物分类

★ 判据

  打乱输入顺序后：
    · 产物【集合】必须完全相同
    · 排序结果必须相同
  任何一项不同 → 存在顺序依赖，需要定位
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
TCMAI_SRC = Path(r"D:\TCMAI\src")
sys.path.insert(0, str(TCMAI_SRC))
sys.path.insert(0, str(STAGE / "api"))
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

from engine import Compound, get_mol, load_engine
from cascade import cascade
from scorer import score_product
import templates as T
from activator import active_rules
from tcm_ro import use_readonly; use_readonly()
from db_utils import find_compounds

eng, rules, profs = load_engine()
cond = T.get_template("煎煮")


def canon(s):
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else None


# 准备底物
# ★ 快速模式只缩小输入，判据不变 ★
import os
QUICK = os.environ.get("DSH_QUICK") == "1"
_HERBS = ("甘草",) if QUICK else ("甘草", "附子", "干姜")
_PER = 8 if QUICK else 15

raw = []
for h in _HERBS:
    for r in find_compounds(h, limit=_PER):
        raw.append(dict(r))
print(f"底物 {len(raw)} 个" + ("（快速模式）" if QUICK else "") + "\n")

PASS, FAIL = [], []


def check(name, same, detail=""):
    (PASS if same else FAIL).append(name)
    print(f"  {'✓' if same else '✗'} {name}   {detail}")


def shuffled(seq, seed):
    out = list(seq)
    random.Random(seed).shuffle(out)
    return out


print("=" * 96)
print("① engine.step —— 单轮：底物池 × 激活规则")
print("=" * 96)


def run_step(seq):
    subs = [Compound(smiles=c["smiles"], name=c["name"],
                     herb=c["herb_name"]) for c in seq if get_mol(c["smiles"])]
    ps = eng.step(subs, cond, 0.15, round_no=1)
    return {canon(p.smiles) for p in ps}


a = run_step(raw)
b = run_step(shuffled(raw, 7))
a.discard(None)
b.discard(None)
check("step 产物集合与底物顺序无关", a == b,
      f"{len(a)} vs {len(b)}  对称差 {len(a ^ b)}")

print()
print("=" * 96)
print("② cascade —— 多轮级联")
print("=" * 96)


def run_cascade(seq):
    subs = [Compound(smiles=c["smiles"], name=c["name"],
                     herb=c["herb_name"]) for c in seq if get_mol(c["smiles"])]
    r = cascade(eng, subs, cond, max_rounds=6, min_new=10, frontier_limit=40)
    return {canon(p.smiles) for p in r.products}, r


a2, ra = run_cascade(raw)
b2, rb = run_cascade(shuffled(raw, 7))
a2.discard(None)
b2.discard(None)
cov = 100 * len(a2 & b2) / max(1, min(len(a2), len(b2)))
check("cascade 同顺序可复现", run_cascade(raw)[0] == a2,
      f"{len(a2)} vs {len(b2)}")
check("cascade 打乱顺序后集合一致", a2 == b2,
      f"覆盖率 {cov:.1f}%  对称差 {len(a2 ^ b2)}")

print()
print("=" * 96)
print("③ 多样性排序 —— 打乱产物顺序，Top-N 应一致")
print("=" * 96)
prods = [p for p in ra.products if not p.is_byproduct]
print(f"  产物池 {len(prods)} 个")


def diverse_top(pool, top=20):
    """调用【真正的实现】而不是本地副本。

    ★ 第一版这里是复刻的副本，结果实现改了、副本没改，
      审计还在报失败 —— 测的不是同一个东西。
      现在直接从 api/predict.py 的 PredictionResult.diverse_ranking 取逻辑。
      为了不构造完整 PredictionResult，用 types.SimpleNamespace 做一个最小壳。
    """
    import types
    sys.path.insert(0, str(STAGE / "api"))
    from predict import PredictionResult
    shell = types.SimpleNamespace(
        products=pool,
        main_products=lambda top=None: [p for p in pool if not p.is_byproduct],
    )
    return [s.smiles for s in
            PredictionResult.diverse_ranking(shell, top=top)]


t1 = diverse_top(prods)
t2 = diverse_top(shuffled(prods, 3))
check("多样性排序与前序无关", t1 == t2,
      f"首个相同={t1[0] == t2[0] if t1 and t2 else '?'}  完全相同={t1 == t2}")

print()
print("=" * 96)
print("④ 条件激活 —— 规则顺序是否稳定")
print("=" * 96)
act = active_rules(rules, profs, cond)
names1 = [r["id"] for r, _s, _w in act]
scores1 = [round(s, 6) for _r, s, _w in act]
act2 = active_rules(list(reversed(rules)), profs, cond)
names2 = [r["id"] for r, _s, _w in act2]
scores2 = [round(s, 6) for _r, s, _w in act2]
check("激活规则集合与规则表顺序无关",
      set(names1) == set(names2) and dict(zip(names1, scores1)) == dict(zip(names2, scores2)),
      f"{len(names1)} 条")

print()
print("=" * 96)
print("⑤ 单个产物打分 —— 是否确定")
print("=" * 96)
if prods:
    sample = prods[:12]
    s1 = [round(score_product(p.smiles, rules[0], 0.5,
                              source_smiles=p.source_smiles)[0], 8) for p in sample]
    s2 = [round(score_product(p.smiles, rules[0], 0.5,
                              source_smiles=p.source_smiles)[0], 8)
          for p in shuffled(sample, 5)]
    check("同一分子打分一致", sorted(s1) == sorted(s2),
          f"{s1[:2]} vs {s2[:2]}")

print()
print("=" * 96)
print(f"结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
for f in FAIL:
    print(f"  ✗ {f}")
print("=" * 96)
