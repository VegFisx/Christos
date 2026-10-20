# -*- coding: utf-8 -*-
r"""
兼容层：用新引擎实现你项目里旧反应引擎的全部公开 API
====================================================

★ 为什么要有这一层

  你的项目里有 7 处调用 `tcm_analyzer.predict_reactions(...)`，
  还有 `get_reactions()` / `REACTIONS` / `cascade_reactions.find_final_products()` /
  `reaction_rules.REACTION_RULES` 等入口。

  如果直接换掉实现，这 7 处全要改。
  **兼容层的思路是：保留公开 API 与返回结构，只把内部实现换成新引擎。**
  于是所有调用方【一行都不用改】。

  这是最安全的搬法——出问题时把兼容层摘掉就回到原状。

★ 提供的 API

    predict_reactions(compounds, min_mw, min_heavy, rule_limits) -> List[Dict]
        返回结构与旧版一致：
            from_herb, from_compound, rxn, formula, smiles, mw
        另有新增键（旧调用方不用也不会坏）：
            rule_id, is_byproduct, confidence, round

    find_final_products(compounds, max_rounds, frontier_limit, min_new) -> Dict
        返回结构与旧版一致：
            products, total, rounds, round_stats, converged, by_round

    get_reactions() -> Dict          旧格式的规则表
    REACTIONS                       旧格式的规则字典
    _LAST_RXN_STATS                 模块级统计（原地更新，保证外部引用能读到）

★ 顺带修掉的旧毛病

    旧 `_valid_product(mol, min_mw=100, min_heavy=10)` 会把 MW<100 或
    重原子<10 的产物【直接删掉】——苯甲酸（9 个重原子）就这么被误杀了。
    新版默认【保留】这些小分子并标记 `is_byproduct=True`。
    想回到旧行为：传 legacy_filter=True。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_STAGE = Path(__file__).resolve().parent.parent
for _d in ("core", "conditions", "rules", "libs", "sources"):
    _p = _STAGE / _d
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound, Engine, get_mol, load_engine    # noqa: E402
from cascade import cascade                                  # noqa: E402
import templates as T                                        # noqa: E402
from activator import active_rules                           # noqa: E402

# 旧模块级统计变量。旧代码 `from tcm_analyzer import _LAST_RXN_STATS` 后
# 读的是同一个 dict 对象，所以必须【原地更新】而不是重新赋值。
_LAST_RXN_STATS: Dict[str, int] = {}

_ENGINE: Optional[Engine] = None
_RULES: List[Dict[str, Any]] = []
_PROFILES: Dict[str, Any] = {}


def _boot():
    global _ENGINE, _RULES, _PROFILES
    if _ENGINE is None:
        _ENGINE, _RULES, _PROFILES = load_engine()
    return _ENGINE, _RULES, _PROFILES


# ---------------------------------------------------------------- 规则表

def get_reactions() -> Dict[str, Dict[str, Any]]:
    """按旧格式返回规则表。

    旧格式：{key: {"name","rxn","desc","irreversible", ...}}
    这里 key 用规则 id，并保留同名键。
    """
    from rdkit.Chem import AllChem
    eng, rules, _ = _boot()
    out: Dict[str, Dict[str, Any]] = {}
    for r in rules:
        if r.get("status") == "disabled":
            continue
        try:
            rxn = AllChem.ReactionFromSmarts(r["smarts"])
        except Exception:
            rxn = None
        out[r["id"]] = {
            "name": r["name"],
            "rxn": rxn,
            "desc": r.get("notes", ""),
            "irreversible": not bool(r.get("reversible", False)),
            "smarts": r["smarts"],
            "category": r.get("category", ""),
            "status": r.get("status"),
        }
    return out


def _reactions_dict() -> Dict[str, Dict[str, Any]]:
    """`REACTIONS` 那种更朴素的格式（只有 name/smarts/desc/irreversible）。"""
    _, rules, _ = _boot()
    return {
        r["id"]: {
            "name": r["name"],
            "smarts": r["smarts"],
            "desc": r.get("notes", ""),
            "irreversible": not bool(r.get("reversible", False)),
        }
        for r in rules if r.get("status") != "disabled"
    }


# ---------------------------------------------------------------- 输入归一化

def _norm_compound(comp) -> Optional[Dict[str, str]]:
    """旧版接受两种输入形式，都要支持。

    · dict:  {"smiles":.., "name":.., "herb_name"|"source":..}
    · tuple: (herb, name, smi)
    """
    if isinstance(comp, dict):
        smi = comp.get("smiles")
        if not smi:
            return None
        return {
            "smiles": smi,
            "name": comp.get("name") or "(无名)",
            "herb": comp.get("herb_name") or comp.get("source") or "",
        }
    if isinstance(comp, (list, tuple)) and len(comp) >= 3:
        herb, name, smi = comp[0], comp[1], comp[2]
        if not smi:
            return None
        return {"smiles": smi, "name": name or "(无名)", "herb": herb or ""}
    return None


# ---------------------------------------------------------------- 主接口

def predict_reactions(compounds,
                      min_mw: float = 100,
                      min_heavy: int = 10,
                      rule_limits: Optional[Dict[str, int]] = None,
                      *,
                      conditions: Any = "煎煮",
                      threshold: float = 0.15,
                      round_no: int = 1,
                      keep_small_molecules: bool = True,
                      legacy_filter: bool = False,
                      ) -> List[Dict]:
    """★ 与旧版同名同签名的替代实现。

    参数
    ----
    compounds           同旧版（dict 或 tuple 列表）
    min_mw, min_heavy   仅在 legacy_filter=True 时生效（见下）
    rule_limits         {规则名: 最多几个产物}，同旧版
    conditions          新增：处理条件（模板名 / Conditions / dict），默认煎煮
    threshold           新增：条件激活阈值
    keep_small_molecules 新增：保留小分子并标记 is_byproduct（默认 True）
    legacy_filter       新增：True 时恢复旧行为（按 min_mw/min_heavy 直接删）

    返回
    ----
    与旧版结构一致的 list[dict]，每项键：
        from_herb, from_compound, rxn, formula, smiles, mw
    （另含 rule_id / is_byproduct / confidence / round，旧代码忽略即可）
    """
    eng, rules, profiles = _boot()

    # ---- 条件 ----
    if isinstance(conditions, str):
        cond = T.get_template(conditions)
    elif hasattr(conditions, "solvent"):        # Conditions 实例
        cond = conditions
    elif isinstance(conditions, dict):
        from model import Conditions
        cond = Conditions.from_dict(conditions)
    else:
        cond = T.get_template("煎煮")

    act = active_rules(rules, profiles, cond, threshold)
    act_score = {r["id"]: s for r, s, _ in act}

    by_name = {r["name"]: r for r in rules}
    limits = dict(rule_limits or {})

    stats: Dict[str, int] = {r["name"]: 0 for r in rules
                             if r.get("status") != "disabled"}
    seen = set()
    products: List[Dict] = []

    for comp in compounds:
        c = _norm_compound(comp)
        if c is None:
            continue
        sub = Compound(smiles=c["smiles"], name=c["name"], herb=c["herb"])
        if get_mol(sub.smiles) is None:
            continue

        for rid, score in act_score.items():
            rule = next((x for x in rules if x["id"] == rid), None)
            if rule is None:
                continue
            limit = limits.get(rule["name"])
            got = eng.apply_rule(rule, sub, score, round_no, cond)
            n = 0
            for p in got:
                if limit is not None and n >= limit:
                    break
                # ---- 旧产物过滤器（默认关掉，就是为了修那个误杀）----
                if legacy_filter:
                    if p.mw < min_mw or p.heavy_atoms < min_heavy:
                        continue
                elif not keep_small_molecules and p.is_byproduct:
                    continue

                key = (p.smiles, sub.name)
                if key in seen:
                    continue
                seen.add(key)
                n += 1
                stats[rule["name"]] = stats.get(rule["name"], 0) + 1
                products.append({
                    # 旧版就有的六个键
                    "from_herb": sub.herb,
                    "from_compound": sub.name,
                    "rxn": rule["name"],
                    "formula": p.formula,
                    "smiles": p.smiles,
                    "mw": p.mw,
                    # 新增（旧调用方不用也不会坏）
                    "rule_id": rule["id"],
                    "is_byproduct": p.is_byproduct,
                    "confidence": getattr(p, "score", None) or score,
                    "round": round_no,
                })

    # ★ 原地更新，保证 `from tcm_analyzer import _LAST_RXN_STATS` 的引用能读到
    _LAST_RXN_STATS.clear()
    _LAST_RXN_STATS.update(stats)
    return products


def find_final_products(compounds: List[Dict],
                        max_rounds: int = 10,
                        frontier_limit: int = 500,
                        min_new: int = 10,
                        *,
                        conditions: Any = "煎煮",
                        **kw) -> Dict:
    """★ 与旧版同名同签名的替代实现。

    返回结构与旧版一致：
        products, total, rounds, round_stats, converged, by_round
    """
    eng, rules, profiles = _boot()

    if isinstance(conditions, str):
        cond = T.get_template(conditions)
    elif hasattr(conditions, "solvent"):
        cond = conditions
    else:
        cond = T.get_template("煎煮")

    seeds = []
    for comp in compounds:
        c = _norm_compound(comp)
        if c is None:
            continue
        if get_mol(c["smiles"]) is None:
            continue
        seeds.append(Compound(smiles=c["smiles"], name=c["name"], herb=c["herb"]))

    res = cascade(eng, seeds, cond,
                  max_rounds=max_rounds,
                  frontier_limit=frontier_limit,
                  min_new=min_new,
                  threshold=0.15)

    products = []
    by_round: Dict[int, List[Dict]] = defaultdict(list)
    for p in res.products:
        rec = {
            "smiles": p.smiles,
            "formula": p.formula,
            "mw": p.mw,
            "rxn": p.rule_name,
            "from_compound": p.source_name,
            "from_herb": p.source_herb,
            "round": p.round,
            "irreversible": not bool(p.reversible),
            # 新增键
            "rule_id": p.rule_id,
            "is_byproduct": p.is_byproduct,
            "confidence": p.score,
        }
        products.append(rec)
        by_round[p.round].append(rec)

    return {
        "products": products,
        "total": len(products),
        "rounds": res.rounds,
        "round_stats": res.round_stats,
        "converged": res.converged,
        "by_round": dict(by_round),
    }


# `REACTIONS` 在旧模块里是个模块级 dict。这里在导入时求值一次即可。
REACTIONS = _reactions_dict()


def reset_state():
    """测试用：清掉模块级统计。"""
    _LAST_RXN_STATS.clear()


if __name__ == "__main__":
    rows = [
        {"smiles": "COC(=O)c1ccccc1", "name": "苯甲酸甲酯", "herb_name": "测试"},
        {"smiles": "Oc1ccc(O)cc1", "name": "对苯二酚", "herb_name": "测试"},
    ]
    ps = predict_reactions(rows)
    print(f"predict_reactions → {len(ps)} 个产物")
    for p in ps[:8]:
        flag = " [副产物]" if p["is_byproduct"] else ""
        print(f"  {p['formula']:<12}{p['rxn']:<16}{p['smiles'][:40]}{flag}")
    print(f"_LAST_RXN_STATS: {len(_LAST_RXN_STATS)} 条规则有产出")
    print(f"get_reactions(): {len(get_reactions())} 条")
    print(f"REACTIONS: {len(REACTIONS)} 条")

    r = find_final_products(rows, max_rounds=3, min_new=5)
    print(f"find_final_products → {r['total']} 个产物，{r['rounds']} 轮，"
          f"收敛={r['converged']}")
