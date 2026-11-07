# -*- coding: utf-8 -*-
r"""对比级联的传播策略：怎么才能既收敛、又不丢有用的产物。

背景：甘草 15 个成分在煎煮条件下，6 轮涨到 1389 个产物且不见顶。
诊断发现贡献最大的规则里一半 priority 只有 0.3（=在煎煮条件下只是猜测）。
把猜测级联下去，不确定性指数放大。

三种策略对比：
  A 现状          只按「不可逆 + 非副产物」传播
  B 加优先级门槛   只有 priority >= 0.5 的规则产物才继续往下反应
  C 加分数门槛     只有产物分数 >= floor 才继续

判据：收敛轮数、产物总数、以及【高分产物有没有被丢掉】。
"""
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for d in ("core", "conditions", "rules", "libs", "sources"):
    p = STAGE / d
    if p.is_dir():
        sys.path.insert(0, str(p))

from engine import Compound, get_mol, load_engine
from scorer import score_product
from cascade import ROUND_DECAY
import templates as T
from herb import compounds_of_herb

engine, rules, profiles = load_engine()
rule_by_id = {r["id"]: r for r in rules}
SEEDS = compounds_of_herb("甘草", limit=15)
COND = T.get_template("煎煮")

print(f"底物: 甘草 {len(SEEDS)} 个 | 条件: {COND.describe()}\n")


def run(strategy, max_rounds=8, min_new=10, frontier_limit=40):
    all_smiles = {s.smiles for s in SEEDS}
    frontier = list(SEEDS)
    collected = {}
    stats = []
    t0 = time.time()

    for rnd in range(1, max_rounds + 1):
        if not frontier:
            break
        step = engine.step(frontier, COND, 0.15,
                           exclude_smiles=all_smiles, round_no=rnd)
        new, prop = [], []
        for p in step:
            if p.smiles in all_smiles:
                continue
            all_smiles.add(p.smiles)
            rule = rule_by_id.get(p.rule_id, {})
            base, _ = score_product(p.smiles, rule, p.activation,
                                    source_smiles=p.source_smiles)
            p.score = round(base * (ROUND_DECAY ** (rnd - 1)), 4)
            collected[p.smiles] = p
            new.append(p)

            if p.reversible or p.is_byproduct:
                continue
            if strategy == "A":
                prop.append(p)
            elif strategy == "B":
                if float(rule.get("priority", 0)) >= 0.5:
                    prop.append(p)
            elif strategy == "C":
                if p.score >= 0.35:
                    prop.append(p)
            elif strategy == "BC":
                if (float(rule.get("priority", 0)) >= 0.5
                        and p.score >= 0.30):
                    prop.append(p)

        stats.append({"round": rnd, "new": len(new), "prop": len(prop),
                      "total": len(collected)})
        if len(prop) < min_new:
            break

        by_rule = defaultdict(list)
        for p in prop:
            by_rule[p.rule_id].append(p)
        if len(prop) > frontier_limit:
            per = max(1, frontier_limit // max(1, len(by_rule)))
            sel = []
            for items in by_rule.values():
                sel.extend(items[:per])
            sel = sel[:frontier_limit]
        else:
            sel = prop
        frontier = [Compound(smiles=p.smiles, name=f"R{rnd+1}", herb="cascade")
                    for p in sel]

    dt = time.time() - t0
    real = [p for p in collected.values() if not p.is_byproduct]
    real.sort(key=lambda p: -p.score)
    return {
        "stats": stats,
        "total": len(collected),
        "rounds": len(stats),
        "converged": len(stats) < max_rounds,
        "seconds": dt,
        "top": real[:10],
        "high_score": [p for p in real if p.score >= 0.5],
    }


print("=" * 96)
print(f"{'策略':<34}{'轮数':>5}{'收敛':>6}{'产物总数':>10}{'高分产物':>10}{'耗时':>8}")
print("-" * 96)
results = {}
LABELS = {
    "A": "A 现状（只按不可逆）",
    "B": "B 加优先级门槛（priority>=0.5）",
    "C": "C 加分数门槛（score>=0.35）",
    "BC": "D 门槛+分数（priority>=0.5 且 >=0.30）",
}
for s in ("A", "B", "C", "BC"):
    r = run(s)
    results[s] = r
    print(f"{LABELS[s]:<34}{r['rounds']:>5}{'是' if r['converged'] else '否':>6}"
          f"{r['total']:>10}{len(r['high_score']):>10}{r['seconds']:>7.1f}s")

print()
print("=" * 96)
print("逐轮明细")
print("=" * 96)
for s in ("A", "B", "BC"):
    r = results[s]
    print(f"\n【{LABELS[s]}】")
    print(f"  {'轮':>3}{'新增':>7}{'可传播':>8}{'累计':>8}")
    for st in r["stats"]:
        print(f"  {st['round']:>3}{st['new']:>7}{st['prop']:>8}{st['total']:>8}")

print()
print("=" * 96)
print("★ 关键检查：加了门槛会不会丢掉高分产物？")
print("=" * 96)
base_high = {p.smiles for p in results["A"]["high_score"]}
for s in ("B", "BC"):
    h = {p.smiles for p in results[s]["high_score"]}
    lost = base_high - h
    print(f"  {LABELS[s]}")
    print(f"    高分产物 {len(h)} 个（现状 {len(base_high)} 个）")
    print(f"    现状有、这里没有的: {len(lost)} 个")
    for smi in list(lost)[:3]:
        print(f"      {smi[:56]}")

print()
print("=" * 96)
print("各策略 Top 5（看排序是否一致）")
print("=" * 96)
for s in ("A", "B", "BC"):
    print(f"\n【{LABELS[s]}】")
    for p in results[s]["top"][:5]:
        print(f"    {p.score:.3f}  {p.formula:<12}{p.rule_name:<16}← {p.source_name[:18]}")
