# -*- coding: utf-8 -*-
"""
chemreact 核心：级联收敛
========================

把产物继续当底物往下反应，直到体系稳定。

设计要点（多数沿用了原 src/cascade_reactions.py 的正确思路）：

  1. ★ **每一轮重新计算条件激活**。
     原 cascade_reactions.py 是开头算一次就固定。但级联过程中体系在变
     （小分子被消耗、pH 可能漂移），条件层应该每轮重算。

  2. ★ **只迭代不可逆反应**。
     可逆反应很快达平衡，不会持续产生新分子。
     把可逆产物也丢进下一轮，级联会虚假膨胀、永不收敛。
     这一条原实现是对的，保留。

  3. ★ **副产物不进前沿**。
     水、甲醇、CO2 这类小分子不当作下一轮底物——
     它们要么是终产物，要么已经过量存在，再迭代没有意义。
     注意：是「不进前沿」，不是「从结果里删掉」，它们仍然出现在产物表中。

  4. ★ **每轮重算分数**。
     第 3 轮的产物和第 1 轮的产物，置信度不该一样——
     离原始成分越远，推断链条越长，不确定性越大。这里用轮数做衰减。

  5. **收敛判据**：一轮下来「新的不可逆产物」少于 min_new 就停。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "rules", _STAGE / "conditions", _STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound, Engine, Product, get_mol     # noqa: E402
from scorer import score_product, rank, assign_thermo     # noqa: E402
from model import Conditions                              # noqa: E402


# 每远一轮，置信度乘这个系数。第 1 轮不衰减。
ROUND_DECAY = 0.85

# ★ 热力学覆盖率低于此值就整体回退启发式。
# 实测教训：中药大分子（附子里的乌头碱类，40~50 个重原子）超出 xTB 可靠范围，
# 覆盖率会低到 10%。这时如果坚持"能算的用真值、算不出的用启发式"，
# 同一张排行榜上就混了两套尺度，**比全部用启发式还糟**。
MIN_THERMO_COVERAGE = 0.5

# ★★ 传播分数门槛：只有分数够高的产物才继续往下反应 ★★
#
# 为什么需要它：甘草 15 个成分在煎煮条件下，8 轮涨到 1736 个产物且不见顶。
# 诊断发现，贡献最大的规则里一半 priority 只有 0.3（=在煎煮条件下只是猜测）——
# 把猜测级联下去，不确定性指数放大。
#
# ★ 为什么是「按分数」而不是「按规则优先级」——这是实测对比出来的：
#
#     策略                     轮数  收敛   产物总数  高分产物
#     A 现状（只按不可逆）        8    否     1736     595
#     B 按 priority >= 0.5       8    否     1378     561 ← 丢了 225 个高分产物
#     C 按 score >= 0.35         7    是     1680     595 ← 一个不丢
#     D 两者都加                 8    否     1392     561 ← 同样丢 225 个
#
#   按优先级设门槛会**截断通路**：高优先级规则固然可靠，但低优先级规则的产物
#   可能继续反应成高分产物，掐掉它们等于砍掉整条路径。
#   而分数里【已经含了 priority】（rule_match 权重 0.30）**又含了轮数衰减**，
#   是比 priority 单独更完整的判据——也是唯一能收敛且不丢高分产物的方案。
#
# 实测（甘草 15 个成分 / 煎煮 / max_rounds=8）：
#
#     门槛    轮数  收敛   产物总数   高分产物(>=0.5)
#     0.00     8    否      1510        573      ← 旧的"只按不可逆"
#     0.25     8    否      1522        573
#     0.35     7    是      1448        573      ← 默认值
#     0.45     5    是      1137        573      ← 想更快可以调到这个
#
#   机制：分数含轮数衰减 0.85^(r-1)，深处产物自然跌破门槛。
#   所以这个门槛本质上定义了「最多追几步推断」——
#   追得越深，累积不确定性越大，这个界是有化学意义的，不是拍脑袋。
MIN_PROPAGATE_SCORE = 0.35


@dataclass
class CascadeResult:
    seeds: List[Compound]
    products: List[Product]
    rounds: int
    round_stats: List[Dict[str, Any]]
    converged: bool
    conditions: Optional[Conditions] = None
    thermo_stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.products)

    def summary(self) -> str:
        lines = []
        c = self.conditions
        lines.append(f"条件：{c.describe() if c else '?'}")
        lines.append(f"起始成分：{len(self.seeds)} 个")
        lines.append("")
        lines.append(f"  {'轮':>3}  {'新增':>6}  {'其中不可逆':>10}")
        for s in self.round_stats:
            lines.append(f"  {s['round']:>3}  {s['new']:>6}  {s['irreversible_new']:>10}")
        lines.append("")
        real = [p for p in self.products if not p.is_byproduct]
        byp = [p for p in self.products if p.is_byproduct]
        lines.append(f"跑了 {self.rounds} 轮，收敛：{'是' if self.converged else '否'}")
        lines.append(f"产物总数 {self.total}  （主体 {len(real)} + 小分子副产物 {len(byp)}）")
        return "\n".join(lines)


def cascade(engine: Engine,
            seeds: Sequence[Compound],
            cond: Conditions,
            max_rounds: int = 3,
            threshold: float = 0.15,
            min_new: int = 10,
            frontier_limit: int = 300,
            thermo=None,
            thermo_top_k: int = 120,
            min_propagate_score: float = MIN_PROPAGATE_SCORE,
            ) -> CascadeResult:
    """迭代反应至稳定态。

    thermo:              core.thermo.Thermo 实例（可选）。
    thermo_top_k:        只给启发式排名前 k 的非副产物算 ΔG。
    min_propagate_score: ★传播门槛★ 只有分数 >= 此值的产物才继续往下反应。
                         这是让级联收敛的关键（见文件顶部常量处的实测对比）。
                         设成 0 就退回旧行为（不收敛）。
    """
    rule_by_id = {r["id"]: r for r in engine.rules}

    all_smiles = {s.smiles for s in seeds}
    frontier: List[Compound] = [s for s in seeds if get_mol(s.smiles) is not None]
    collected: Dict[str, Product] = {}
    round_stats: List[Dict[str, Any]] = []

    for r in range(1, max_rounds + 1):
        if not frontier:
            break

        # ★ 每轮重新评估条件、重新算激活（由 engine.step 内部完成）
        step_products = engine.step(frontier, cond, threshold,
                                    exclude_smiles=all_smiles, round_no=r)

        new_this_round: List[Product] = []
        irreversible_new: List[Product] = []
        below_floor = 0

        for p in step_products:
            if p.smiles in all_smiles:
                continue
            all_smiles.add(p.smiles)

            # ★ 当场打分——传播判断要用它。
            #   分数 = 五因子加权 × 轮数衰减，其中已含 rule priority 和条件匹配度。
            rule = rule_by_id.get(p.rule_id, {})
            base, _d = score_product(p.smiles, rule, p.activation,
                                     source_smiles=p.source_smiles)
            p.score = round(base * (ROUND_DECAY ** (r - 1)), 4)

            collected[p.smiles] = p
            new_this_round.append(p)

            # ★ 传播条件：不可逆 + 非副产物 + 分数达门槛
            if p.reversible or p.is_byproduct:
                continue
            if p.score < min_propagate_score:
                below_floor += 1
                continue
            irreversible_new.append(p)

        round_stats.append({
            "round": r,
            "new": len(new_this_round),
            "irreversible_new": len(irreversible_new),
            "below_floor": below_floor,
        })

        if len(irreversible_new) < min_new:
            break

        frontier = _sample_frontier(irreversible_new, frontier_limit, r + 1)

    # ---- 最终评分 ----
    # 注意：循环里已经打过分（传播判断要用），这里重算一遍是因为
    # 上面用的是启发式 stability，而下面可能用真 ΔG 覆盖。
    pool = list(collected.values())
    decay = {id(p): (ROUND_DECAY ** max(p.round - 1, 0)) for p in pool}

    for p in pool:
        rule = rule_by_id.get(p.rule_id, {})
        base, _d = score_product(p.smiles, rule, p.activation,
                                 source_smiles=p.source_smiles)
        p.score = round(base * decay[id(p)], 4)

    # ★ 第二遍：热力学。
    # 只给启发式排出来的 top-k 算 ΔG——
    # 实测：245 个产物全算要 15 分钟且大部分超预算失败，
    # 而真正需要精确排序的只有头部。
    tstats: Dict[str, Any] = {"skipped": "未启用或 xTB 不可用"}
    if thermo is not None and getattr(thermo, "available", False) and pool:
        head = rank(pool, top_k=thermo_top_k, include_byproducts=False)
        tstats = assign_thermo(head, thermo, rule_by_id)
        tstats["top_k"] = len(head)
        tstats["pool"] = len(pool)

        n_ok = sum(1 for p in head if p.stability is not None)
        coverage = (n_ok / len(head)) if head else 0.0
        tstats["coverage"] = round(coverage, 3)

        # ★ 覆盖率不足就整体回退。
        # 理由是实测才发现的一个隐患：如果一部分产物用真 ΔG、另一部分用结构启发式，
        # 两者尺度不同，放在同一张排行榜上**不可比**——那比全部用启发式还糟。
        # 一致性优先于局部精度。
        if coverage < MIN_THERMO_COVERAGE:
            for p in pool:
                p.stability = None
                p.dg_kj = None
            tstats["reverted"] = (
                f"ΔG 覆盖率仅 {coverage:.0%}（低于 {MIN_THERMO_COVERAGE:.0%}），"
                f"为避免两套尺度混用，整体回退启发式"
            )
        else:
            for p in pool:
                if p.stability is None:
                    continue
                rule = rule_by_id.get(p.rule_id, {})
                base, _d = score_product(p.smiles, rule, p.activation,
                                         source_smiles=p.source_smiles,
                                         stability_override=p.stability)
                p.score = round(base * decay[id(p)], 4)

    converged = bool(round_stats) and round_stats[-1]["irreversible_new"] < min_new

    return CascadeResult(
        seeds=list(seeds),
        products=rank(pool),
        rounds=len(round_stats),
        round_stats=round_stats,
        converged=converged,
        conditions=cond,
        thermo_stats=tstats,
    )


def _sample_frontier(products: Sequence[Product], limit: int,
                     next_round: int) -> List[Compound]:
    """按反应类型均衡采样，避免某一类规则（比如羟基氧化）淹没前沿。

    ★★ 必须确定性排序 ★★

    实测事故：把同一批成分的【输入顺序】打乱后重跑级联，
    输出只有 22~36% 自重叠（同一个引擎、同一批分子！）。

    根因：这里按【插入顺序】取前 per_rule 个，而插入顺序取决于
          输入成分的顺序 —— 于是"挑谁进前沿"变成了随机的。

    修法（两处都要确定）：
      1. 每条规则内部：按【分数降序、同分按 SMILES】排序后取前 per_rule 个
         （顺带带来好处：高置信产物优先进入前沿）
      2. 规则之间：轮转取（round-robin），规则按 id 排序
         —— 既保证每条规则都有机会，又不依赖 dict 的插入顺序

    修完之后：同一批成分不论以什么顺序传入，级联输出完全一致。
    """
    if len(products) <= limit:
        selected = list(products)
    else:
        by_rule: Dict[str, List[Product]] = defaultdict(list)
        for p in products:
            by_rule[p.rule_id].append(p)

        def _key(p: Product):
            return (-(p.score or 0.0), p.smiles)

        buckets = {rid: sorted(items, key=_key)
                   for rid, items in by_rule.items()}
        per_rule = max(1, limit // max(1, len(buckets)))

        # 轮转：第 0 轮每规则各取 1 个，第 1 轮再各取 1 个……
        selected = []
        depth = 0
        max_depth = max(len(v) for v in buckets.values())
        while len(selected) < limit and depth < max_depth:
            for rid in sorted(buckets):
                if depth < len(buckets[rid]):
                    selected.append(buckets[rid][depth])
                    if len(selected) >= limit:
                        break
            depth += 1

    return [Compound(smiles=p.smiles, name=f"R{next_round} 中间体",
                     herb=p.source_herb, source="cascade")
            for p in selected]
