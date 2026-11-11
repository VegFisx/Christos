# -*- coding: utf-8 -*-
r"""第十四轮 / 任务③：TCMAI 接入桥 —— 让 TCMAI 用上 SmartReact 引擎。

⚠ 纪律：`D:\TCMAI` 只读。本文件只【读】tcm.db（通过 TCMAI 的 db_utils），
  所有产出都在 chemreact-staging。真正的落地补丁见
  `reports/第十四轮-TCMAI接入方案.md`（要用户确认后才动 TCMAI）。

接口对齐（实测自 D:\TCMAI\src\tcm_analyzer.py:288-352）：
  输入 compounds: list[dict]，键 smiles / name / herb_name（或 source）
  输出 products : list[dict]，键 from_herb / from_compound / rxn / formula / smiles / mw
  本桥的 predict_reactions() 保持同一输入输出形状，替换掉 10 条手写 SMARTS 的那一套。

诚实性约束（必须跟着接口一起给出去）：
  见 confidence_report()：ORD 上的召回只有 ~28.6%，HTE 真实失败条件上的
  假阳性率 94.9%、条件门控 AUC 0.530 —— 所以本桥的输出**只能当候选清单/排雷**，
  不能当"会不会发生"的判定。这句话会同时打印在 demo 里。

用法（只读演示）:
  python tcmai_bridge.py --demo 甘草
  python tcmai_bridge.py --confidence
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
TCMAI = Path(r"D:\TCMAI")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "libs", STAGE / "tools", TCMAI / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound as CRCompound           # noqa: E402
from model import Conditions, solvent_class          # noqa: E402
from smartreact_engine import SmartReactEngine       # noqa: E402

# 煎煮默认条件（与 TCMAI 的「煎煮」模板一致：水 / 100 °C / 60 min / pH 6.5）
# 第 144 轮修 C8：不再手写一份，改为从 conditions/templates.py 的「煎煮」档取，
# 避免两处常量各自漂移（导出给外部调用方时必须与引擎里的那一档同源）。
def _default_conditions() -> Conditions:
    try:
        import templates as _tpl                      # conditions/ 在 sys.path 上
        spec = (_tpl.TEMPLATES or {}).get("煎煮") or {}
        return Conditions(solvent=str(spec.get("solvent") or "water"),
                          temperature=float(spec.get("temperature") or 100.0),
                          time_min=float(spec.get("time_min") or 60.0),
                          pH=float(spec.get("pH") if spec.get("pH") is not None else 6.5))
    except Exception as _ex:                          # noqa: BLE001 —— 取不到就退回历史值并说明
        print(f"   [warn] 读到「煎煮」条件档失败（{type(_ex).__name__}: {_ex}），"
              f"退回内置值 water/100/60/6.5", file=sys.stderr)
        return Conditions(solvent="water", temperature=100.0, time_min=60.0, pH=6.5)


DEFAULT_CONDITIONS = _default_conditions()

# ★ 级联用：哪些反应类型算"不可逆"（会驱动体系继续反应）★
#   这是【我的判断/建模选择】，不是 ORD 实测值；TCMAI 的 cascade_reactions 需要这个标记。
#   基于化学常识挑了明显不可逆的类别；其余默认 False（保守，宁可少迭代）。
IRREVERSIBLE_CLASSES = {
    "B-H", "suzuki", "ullmann_X", "ullmann_phenol", "chan_lam",
    "amide_coupling", "esterification", "ester_sulfonic_schotten_baumann",
    "reductive_amination_aldehyde", "reductive_amination_ketone",
    "C_C_decarboxylation", "deoxygenative_coupling",
    "mitsunobu", "williamson", "snar_amine", "snar_alcohol", "snar_thiol",
    "click", "triazole_synthesis_2", "urea_formation", "amine_acetylation",
    "amine_sulfonation", "imidazole_condensation_acid", "imidazole_condensation_amine",
    "cross_electrophile_coupling", "negishi_batch", "negishi_insitu",
}

_ENGINE: Optional[SmartReactEngine] = None


def get_engine(gate_conditions: bool = True) -> SmartReactEngine:
    """单例（SmartReact 初始化要几秒，别每次新建）。"""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = SmartReactEngine(gate_conditions=gate_conditions)
    return _ENGINE


def get_reactions() -> Dict[str, Dict[str, Any]]:
    """兼容 TCMAI `tcm_analyzer.get_reactions()` 的调用面。

    ⚠ 与 TCMAI 旧版不同：本引擎每个"反应类型"背后是几十~上千条模板，
       **没有单一的 `rxn`（ReactionFromSmarts）对象**。
       所以调用方不能再用 `rinfo['rxn'].RunReactants(...)` —— 必须换成
       `predict_reactions()`（本模块已提供同形状输出）。
       这里返回的 dict 只保留 cascade 需要的 `name` / `irreversible` 字段。
    """
    eng = get_engine()
    return {r["id"]: {"name": r["name"], "rxn": None,
                      "n_templates": r.get("n_templates"),
                      "irreversible": r["id"] in IRREVERSIBLE_CLASSES}
            for r in eng.rules}


def predict_reactions(compounds: List[Dict],
                      conditions: Optional[Conditions] = None,
                      min_mw: float = 100.0,
                      min_heavy: int = 10,
                      gate_conditions: bool = True) -> List[Dict]:
    """与 TCMAI `predict_reactions()` 同形状：见文件顶部接口说明。

    额外多给三个键（不会影响旧调用方）：`activation`（条件门控分数）、
    `category`、`gate_note`（被降权/判零的原因）。
    """
    cond = conditions or DEFAULT_CONDITIONS
    eng = get_engine(gate_conditions=gate_conditions)
    comps: List[CRCompound] = []
    meta: Dict[str, Dict[str, str]] = {}
    for c in compounds:
        if not isinstance(c, dict):
            continue
        smi = c.get("smiles")
        if not smi:
            continue
        name = c.get("name", "(无名)")
        herb = c.get("herb_name") or c.get("source", "")
        comps.append(CRCompound(smiles=smi, name=name, herb=herb, source="herb"))
        meta[CRCompound(smiles=smi, name=name, herb=herb, source="herb").to_dict()["smiles"]] = {
            "name": name, "herb": herb}
    if len(comps) < 2:
        return []

    prods = eng.step(comps, cond, round_no=1)
    out, seen = [], set()
    for p in prods:
        if p.mw < min_mw or p.heavy_atoms < min_heavy:
            continue
        key = (p.smiles, p.source_name)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "from_herb": p.source_herb,
            "from_compound": p.source_name,
            "rxn": p.rule_name,
            "formula": p.formula,
            "smiles": p.smiles,
            "mw": round(p.mw, 1),
            # —— 扩展字段（本桥新增）——
            "activation": round(float(getattr(p, "activation", 0.0)), 3),
            "category": getattr(p, "category", ""),
            "gate_note": "",
        })
    return out


def predict_for_herb(herb_name: str, conditions: Optional[Conditions] = None,
                     limit: int = 200) -> Dict[str, Any]:
    """只读演示：从 tcm.db 取药材成分 -> 预测产物。"""
    from tcm_ro import use_readonly; use_readonly(); from db_utils import find_compounds  # 来自 D:\TCMAI\src（只读）
    rows = find_compounds(herb_name, limit=limit)
    prods = predict_reactions(rows, conditions)
    types: Dict[str, int] = {}
    for p in prods:
        types[p["rxn"]] = types.get(p["rxn"], 0) + 1
    return {"herb": herb_name, "compounds": len(rows),
            "cond": (conditions or DEFAULT_CONDITIONS).describe(),
            "n_products": len(prods), "types": dict(sorted(types.items(), key=lambda kv: -kv[1])),
            "products": prods}


def confidence_report() -> Dict[str, Any]:
    """本引擎现在的可信度（全部实测数字，来自 reports/）。"""
    rep: Dict[str, Any] = {
        "ord_coverage_28.6pct": "SmartReact 9770 模板对 ORD 真实文献的泛化命中率（口径见 "
                                "tools/validate_ord_coverage.py）",
    }
    hte = STAGE / "reports" / "hte_negatives_summary.json"
    if hte.exists():
        d = json.loads(hte.read_text(encoding="utf-8"))
        a = d.get("A_template_library_unconditional", {})
        b = d.get("B_condition_gate", {})
        rep["hte_recall_positive_control"] = a.get("pos_recall")
        rep["hte_false_positive_rate"] = a.get("neg_false_positive_rate")
        rep["hte_negatives_evaluated"] = a.get("neg_pairs_evaluated")
        rep["hte_condition_gate_auc"] = b.get("auc")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", metavar="药材", help="只读演示：药材 -> 产物")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--confidence", action="store_true", help="只打印可信度数字")
    args = ap.parse_args()

    print("=" * 96)
    print("TCMAI 接入桥（只读；未修改 D:\\TCMAI）")
    print("=" * 96)
    rep = confidence_report()
    for k, v in rep.items():
        print(f"  {k:<32} {v}")
    print("  ⚠ 结论：只能当候选清单/排雷，不能当『会不会发生』的判定。")

    if args.confidence or not args.demo:
        return 0
    res = predict_for_herb(args.demo, limit=args.limit)
    print()
    print(f"【{res['herb']}】成分 {res['compounds']} 个   条件 {res['cond']}")
    print(f"  预测产物 {res['n_products']} 个，涉及反应类型 {len(res['types'])} 类:")
    for t, n in list(res["types"].items())[:12]:
        print(f"    {t:<34} {n}")
    print("  前 8 个产物:")
    for p in res["products"][:8]:
        print(f"    {p['from_compound'][:16]:<18} {p['rxn']:<26} {p['smiles'][:52]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
