# -*- coding: utf-8 -*-
"""
chemreact 核心：产物评分
========================

对应项目简报 §9：

    score = w1*rule_match + w2*condition_match + w3*stability
          + w4*atom_conservation + w5*stereo

★ 诚实说明：五个因子里有三个是扎实的，两个是占位。

  · rule_match          扎实。就是规则自己的 priority（人给的）。
  · condition_match     扎实。来自条件层，有实测支撑（见 ROUND3 结论）。
  · atom_conservation   扎实。规则是否真的配平过——校验器 24/24 全过，
                        所以目前恒为 1.0；留着这个因子是为了将来加规则时仍能区分。
  · stability           **占位**。真正的稳定性应该来自反应 ΔG——
                        而你项目里 `src/thermo_xtb.py` 正好能算
                        （GFN2-xTB + 水相 GBSA，而且是真量子化学）。
                        它现在是个没人调用的孤儿模块。建议尽快接上，
                        替换掉这里的启发式。
  · stereo              **偏弱**。只能做"手性中心有没有丢"的粗判，
                        不能判"手性对不对"。真正的立体化学要靠 RDChiral 的
                        模板 + 人工核对。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rdkit import Chem
from rdkit.Chem import Descriptors

# 权重：先给经验值，等有了测试集（简报 §11 的 100~500 条）再标定。
WEIGHTS = {
    "rule": 0.30,
    "condition": 0.30,
    "stability": 0.20,
    "conservation": 0.10,
    "stereo": 0.10,
}

# 不稳定的结构基元（SMARTS）→ 扣分幅度
UNSTABLE_MOTIFS: List[Tuple[str, float, str]] = [
    ("[OX2,OX1-][OX2,OX1-]", 0.6, "过氧键 O-O"),
    ("[CX3]=[CX3]=[CX3]", 0.5, "累积双键"),
    ("[CX3H1]=[OX1]", 0.15, "醛基（易被氧化）"),
    ("[NX2]=[NX2]", 0.3, "偶氮/重氮"),
    ("[CX4]1[CX4][CX4]1", 0.4, "三元碳环（张力大）"),
    ("[#6;r3]", 0.25, "三元环"),
]


def _mol(smiles: str) -> Optional[Chem.Mol]:
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        return None
    try:
        Chem.SanitizeMol(m)
    except Exception:
        return None
    return m


# ---------------------------------------------------------------- 各因子

def rule_match_score(rule: Dict[str, Any]) -> float:
    return float(rule.get("priority", 0.5))


def condition_match_score(activation: float, rule: Dict[str, Any]) -> float:
    """条件层给的是「木桶短板 × priority」，这里要把 priority 除掉，
    还原成纯条件匹配度，免得同一个因子被算两遍。"""
    prio = max(float(rule.get("priority", 0.5)), 1e-6)
    return min(activation / prio, 1.0)


def atom_conservation_score(rule: Dict[str, Any]) -> float:
    """规则是否通过过配平校验。

    全库 24/24 通过，所以实际恒为 1.0。
    但保留这个因子：将来加规则时，没通过校验的规则会被这里压下去，
    而不是悄悄混进高分行列。
    """
    return 0.0 if rule.get("status") == "suspect_unbalanced" else 1.0


def stability_score(smiles: str) -> Tuple[float, List[str]]:
    """★占位实现★ 只做结构基元的粗筛，不是热力学稳定性。

    真正的做法：接 src/thermo_xtb.py 算反应 ΔG。
    """
    m = _mol(smiles)
    if m is None:
        return 0.0, ["分子无法解析"]

    score = 0.85
    notes: List[str] = []
    for smarts, penalty, label in UNSTABLE_MOTIFS:
        patt = Chem.MolFromSmarts(smarts)
        if patt is not None and m.HasSubstructMatch(patt):
            score -= penalty
            notes.append(f"含{label} -{penalty}")
    return max(0.0, round(score, 3)), notes


def stereo_score(source_smiles: str, product_smiles: str) -> Tuple[float, List[str]]:
    """手性中心「有没有丢」的粗判。

    1.0 = 底物无手性中心，或产物的手性中心都被明确定义
    0.5 = 产物有未定义的手性中心（可能丢立体化学）
    不完全可靠：只判"定没定义"，不判"对不对"。
    """
    src = _mol(source_smiles)
    prod = _mol(product_smiles)
    if prod is None:
        return 0.0, ["产物无法解析"]

    n_undef = len(Chem.FindMolChiralCenters(
        prod, includeUnassigned=True, useLegacyImplementation=False))
    n_defined = len(Chem.FindMolChiralCenters(
        prod, includeUnassigned=False, useLegacyImplementation=False))

    if n_undef == 0 and n_defined == 0:
        return 1.0, []
    if n_defined >= n_undef and n_undef > 0:
        return 1.0, []
    if n_undef > n_defined:
        return 0.5, [f"产物有 {n_undef - n_defined} 个未定义手性中心"]
    return 1.0, []


# ---------------------------------------------------------------- 综合评分

def score_product(smiles: str, rule: Dict[str, Any], activation: float,
                  source_smiles: str = "",
                  stability_override: Optional[float] = None,
                  ) -> Tuple[float, Dict[str, Any]]:
    """返回 (总分 0~1, 各因子明细)。

    stability_override：由 core/thermo.py 算出的热力学稳定性（0~1）。
    传了就用真值；没传就退回结构启发式。
    """
    s_rule = rule_match_score(rule)
    s_cond = condition_match_score(activation, rule)
    if stability_override is not None:
        s_stab, stab_notes = float(stability_override), ["来自 xTB 热力学"]
    else:
        s_stab, stab_notes = stability_score(smiles)
    s_cons = atom_conservation_score(rule)
    s_stereo, stereo_notes = stereo_score(source_smiles, smiles)

    total = (WEIGHTS["rule"] * s_rule
             + WEIGHTS["condition"] * s_cond
             + WEIGHTS["stability"] * s_stab
             + WEIGHTS["conservation"] * s_cons
             + WEIGHTS["stereo"] * s_stereo)

    detail = {
        "rule_match": round(s_rule, 3),
        "condition_match": round(s_cond, 3),
        "stability": s_stab,
        "atom_conservation": s_cons,
        "stereo": s_stereo,
        "notes": stab_notes + stereo_notes,
    }
    return round(total, 4), detail


# ---------------------------------------------------------------- 热力学接入

# ★★ 实测发现的系统性偏差（必须知道，否则会误用）★★
#
# 拿 xTB 算几个教科书反应，结果：
#   乙醇脱水成乙烯      +69.3 kJ/mol   符号对（吸热）✓
#   乙烯水合成乙醇      -69.3 kJ/mol   完美对称 ✓
#   丙酮加氢成异丙醇    -52.1 kJ/mol   符号对 ✓
#   乙酸乙酯水解        +13.2 kJ/mol   ★符号错★（实验约 -9）
#   苯甲酸甲酯水解      +16.5 kJ/mol   ★符号错★
#   葡萄糖苷水解        +11.0 kJ/mol   ★符号错★
#
# 结论：**水解类系统性偏高约 +20 kJ/mol**。
# 最可能的原因：水既是反应物又是溶剂，而 GBSA 隐式溶剂模型处理不了
# "参与反应的水分子"——它把水当成孤立分子泡在隐式溶剂里。
#
# 因此本模块的处理方式是：
#   · 绝对值只作参考，不做"能不能发生"的判据
#   · ★ 在同一规则（同一类反应）内部做相对排序 ★
#     系统偏差在同组内会相互抵消，这才是 ΔG 在这里的正确用法
#
# 想让绝对值可信，得换显式溶剂模型或更高精度方法——超出当前范围。

# 同组样本少于这个数时，相对排序没有统计意义，退回绝对映射
MIN_GROUP_FOR_RELATIVE = 3


def stability_from_dg_absolute(dg_kj: float) -> float:
    """绝对映射。因为有系统性偏差，只用在不做相对排序的兜底场景。"""
    lo, hi = -30.0, 20.0
    if dg_kj <= lo:
        return 1.0
    if dg_kj >= hi:
        return 0.0
    return round((hi - dg_kj) / (hi - lo), 4)


def assign_thermo(products, thermo, rule_by_id: Dict[str, Any]) -> Dict[str, Any]:
    """给产物批量算反应 ΔG，并在同一规则内部做相对归一化。

    直接改写入参 product 对象的 dg_kj / stability 字段。

    返回统计信息，便于观察命中率与耗时。
    """
    stats = {"attempted": 0, "computed": 0, "failed": 0, "groups": 0,
             "relative_groups": 0, "skipped_unreliable": 0}

    if thermo is None or not getattr(thermo, "available", False):
        stats["skipped"] = "thermo 不可用"
        return stats

    # ★★ 跳过「气相 ΔG 已知不可靠」的规则 ★★
    #
    # 实测（tools/refine_hydrolysis_boundary.py）：
    #   水解类反应的气相 ΔG 【符号系统性错误】——
    #     酯水解   +13.2（化学应 ≈ -4）    糖苷水解 +11.0
    #     酰胺水解 +34.6                    亚胺水解 +13.0
    #     内酰胺开环 +88.3
    #   而加成型/张力释放型是对的：
    #     环氧化物开环 -28.5 ✓   烯烃水合 -69.3 ✓   烯酮水合 -15.4 ✓
    #
    #   原因：水解由【溶剂化熵】驱动，气相 xTB 算不出这一项。
    #
    # 后果：如果照用，会给糖苷/酯水解产物打 0.07~0.18 的低分 ——
    #       而这两类恰恰是中药煎煮里最常发生的反应。
    #
    # 所以：**不让一个已知系统性错误的信号去影响排序**。
    # 哪些规则跳过，写在规则库自己身上（`thermo_unreliable: true`），
    # 而不是硬编码在代码里 —— 这样知识跟着数据走。
    n_skip = 0
    kept = []
    for p in products:
        rule = rule_by_id.get(p.rule_id)
        if rule is not None and rule.get("thermo_unreliable"):
            n_skip += 1
            p.dg_kj = None
            p.stability = None
            continue
        kept.append(p)
    stats["skipped_unreliable"] = n_skip
    products = kept

    # 同一个 (规则, 底物, 产物组) 只需要算一次
    cache: Dict[tuple, Optional[float]] = {}
    by_rule: Dict[str, list] = {}

    for p in products:
        rule = rule_by_id.get(p.rule_id)
        if rule is None or not p.co_products:
            continue
        stats["attempted"] += 1

        key = (p.rule_id, p.source_smiles, p.co_products)
        if key not in cache:
            eq = thermo.build_equation(rule, p.source_smiles, p.co_products)
            cache[key] = thermo.reaction_dg(*eq) if eq else None
            if cache[key] is not None:
                stats["computed"] += 1
        dg = cache[key]

        if dg is None:
            stats["failed"] += 1
            continue
        p.dg_kj = round(dg, 2)
        by_rule.setdefault(p.rule_id, []).append(p)

    # ★ 同规则内部相对归一化：把系统偏差抵消掉
    for rid, group in by_rule.items():
        stats["groups"] += 1
        dgs = [p.dg_kj for p in group if p.dg_kj is not None]
        if len(dgs) < MIN_GROUP_FOR_RELATIVE:
            for p in group:
                p.stability = stability_from_dg_absolute(p.dg_kj)
            continue

        stats["relative_groups"] += 1
        lo, hi = min(dgs), max(dgs)
        span = hi - lo
        for p in group:
            if span < 1e-6:
                p.stability = 0.5          # 全组一样，无区分度
            else:
                # ΔG 越负越有利 → 分数越高
                p.stability = round((hi - p.dg_kj) / span, 4)

    return stats


# ---------------------------------------------------------------- 排序

def rank(products, top_k: Optional[int] = None, include_byproducts: bool = False):
    """按分数降序排；默认把副产物压到最后（但不删除）。

    ★ 注意：这里和原 tcm_analyzer.py 的 _valid_product 有本质区别——
      那边是把苯甲酸这类小分子**直接删掉**（9 个重原子 < 10），
      这边只是**排到后面**。数据永远不丢。
    """
    pool = list(products)
    if not include_byproducts:
        pool.sort(key=lambda p: (p.is_byproduct, -p.score))
    else:
        pool.sort(key=lambda p: -p.score)
    return pool[:top_k] if top_k else pool
