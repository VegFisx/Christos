# -*- coding: utf-8 -*-
r"""
chemreact 前端入口：从「方剂 / 药材 / SMILES + 条件」到产物清单
==============================================================

这是把前面所有模块串起来的那一层，也是唯一"看得见"的那一层：

    输入（方剂文本 / 药材名列表 / 直接 SMILES）  +  处理条件
        ↓
    方剂解析 → 药材名 + 剂量        （复用 D:\TCMAI\src\parse_peifang.py，只读）
        ↓
    成分采集                        （core 之外的 sources/herb.py，只读 tcm.db）
        ↓
    条件激活                        （conditions/）
        ↓
    级联收敛                        （core/cascade.py）
        ↓
    评分排序 + 来源追溯              （core/scorer.py，每个产物都带）
        ↓
    产物清单

用法（命令行）：
    python predict.py --herbs 附子 干姜 甘草 --condition 煎煮
    python predict.py --formula "甘草2两（炙），干姜1两半，附子1枚（生用）"
    python predict.py --smiles "COC(=O)c1ccccc1" --condition 醇提
    python predict.py --list-conditions
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _d in ("core", "conditions", "rules", "libs", "sources"):
    _p = _STAGE / _d
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound, Engine, load_engine          # noqa: E402
from cascade import CascadeResult, cascade                # noqa: E402
from scorer import rank                                    # noqa: E402
from model import Conditions                               # noqa: E402
import templates as T                                      # noqa: E402
from activator import active_rules, explain                # noqa: E402
from herb import compounds_of_herb, compounds_from_smiles, list_herbs  # noqa: E402

TCMAI_SRC = Path(r"D:\TCMAI\src")


# ---------------------------------------------------------------- 输入解析

def parse_formula_text(text: str) -> List[Dict[str, Any]]:
    """把方剂文本解析成 [{herb, dose, process}]。

    ★ 优先复用你项目里现成的 `src/parse_peifang.py`（只读导入）。
      它处理了古方剂量（"2两"、"1两半"、"1枚"）和炮制（括号内容），
      比我重写一遍靠谱。取不到时才退回一个简易解析。
    """
    try:
        if str(TCMAI_SRC) not in sys.path:
            sys.path.insert(0, str(TCMAI_SRC))
        from parse_peifang import parse_peifang  # type: ignore
        out = parse_peifang(text)
        if out:
            for item in out:
                item["_parser"] = "src/parse_peifang.py（复用你项目里的）"
            return out
    except Exception:
        pass

    # 退路：按标点切分，尽量认出末尾的剂量
    import re
    parts = re.split(r"[，,、；;。]", text or "")
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.search(r"([0-9一二三四五六七八九十百]+)\s*"
                      r"(两|钱|分|枚|升|合|斤|克|片|个|条|寸|粒|只|束|把|撮)", p)
        if m:
            out.append({"herb": p[:m.start()].strip(), "dose": m.group(0),
                        "process": None, "raw": p,
                        "_parser": "内置简易解析（未取到你项目的解析器）"})
        else:
            out.append({"herb": p, "dose": None, "process": None, "raw": p,
                        "_parser": "内置简易解析"})
    return out


# ---------------------------------------------------------------- 结果对象

@dataclass
class PredictionResult:
    inputs: Dict[str, Any]
    conditions: Conditions
    compounds: List[Compound]
    herb_counts: Dict[str, int]
    active_rules: List[Dict[str, Any]]
    cascade: CascadeResult
    n_rules: int = 0
    elapsed: float = 0.0

    # -------------------------------------------------- 视图

    @property
    def products(self):
        return self.cascade.products

    def main_products(self, top: Optional[int] = None):
        """只取主体产物（不含水/甲醇/CO2 这类小分子副产物）。"""
        pool = [p for p in self.products if not p.is_byproduct]
        return pool[:top] if top else pool

    def diverse_products(self, top: Optional[int] = None,
                         by: str = "formula"):
        """去重视图：同一个分子式的多个异构体只留最高分的一个。

        ★ 为什么需要：羟基氧化这类规则会在分子的**不同位点**分别氧化，
          生成一堆**分子式相同、SMILES 不同**的异构体。
          化学上它们确实是不同分子，但直接铺在清单里太吵，
          而且会淹没其他反应类型的产物。
          这里按分子式归并，并记下"这一组有几个异构体"，
          信息不丢，但可读性大幅提升。
        """
        best: Dict[Any, list] = {}
        for p in self.main_products():
            key = p.formula if by == "formula" else (p.formula, p.rule_name)
            cur = best.get(key)
            if cur is None:
                best[key] = [p, 1]
            else:
                cur[1] += 1
                if p.score > cur[0].score:
                    cur[0] = p
        out = sorted(best.values(), key=lambda x: -x[0].score)
        return out[:top] if top else out

    def diverse_ranking(self, top: int = 20, penalty: float = 0.12,
                        include_byproducts: bool = False):
        """★多样性排序★：不让单一反应类型霸榜。

        实测动机：甘草的 Top 20 里，`羟基氧化` 一种规则能占十几行——
        不是因为它最可信，而是因为它作用位点最多（每个仲醇都能氧化）。
        这样铺出来的清单**读不出"这个方剂会发生哪几类反应"**。

        做法（贪心 + 边际惩罚，类似 MMR）：每选走一个产物，
        同一条规则的其余产物分数就扣一点。扣多少由 penalty 决定。

        ★ 必须按 SMILES 排序后再挑 ★
          实测：1293 个产物只有 120 个不同分数值 —— **98% 的产物存在并列**。
          不排序的话，并列时按列表顺序破平，而列表顺序会变，
          于是两种顺序跑出来的 Top-20 只有 5/20 相同（3/4 是任意的）。
          按 SMILES 排序 + 只在【严格大于】时替换 → 并列时取 SMILES 最小的那个，
          结果与输入顺序无关。

        注意：**这不改变任何产物的原始分数**，只影响展示顺序。
        `p.score` 始终是真实分数，这里只是挑一个更有信息量的 Top-N。
        """
        pool = [p for p in self.products
                if include_byproducts or not p.is_byproduct]
        remaining = sorted(pool, key=lambda p: p.smiles)
        selected: List[Any] = []
        used: Counter = Counter()

        while remaining and len(selected) < top:
            best = None
            best_adj = None
            # remaining 始终是排序过的 → 并列时自然取 SMILES 最小的
            for p in remaining:
                adj = p.score - penalty * used[p.rule_id]
                if best_adj is None or adj > best_adj:
                    best, best_adj = p, adj
            selected.append(best)
            used[best.rule_id] += 1
            remaining.remove(best)
        return selected

    def byproducts(self):
        return [p for p in self.products if p.is_byproduct]

    def by_herb(self) -> Counter:
        """统计产物来自哪味药（追溯用）。"""
        c: Counter = Counter()
        for p in self.main_products():
            c[p.source_herb or "(未知)"] += 1
        return c

    def by_rule(self) -> Counter:
        c: Counter = Counter()
        for p in self.main_products():
            c[p.rule_name] += 1
        return c

    def by_round(self) -> Counter:
        c: Counter = Counter()
        for p in self.main_products():
            c[p.round] += 1
        return c

    def to_json(self) -> Dict[str, Any]:
        return {
            "inputs": self.inputs,
            "conditions": self.conditions.to_dict(),
            "herb_counts": self.herb_counts,
            "n_compounds": len(self.compounds),
            "n_active_rules": len(self.active_rules),
            "cascade": {
                "rounds": self.cascade.rounds,
                "converged": self.cascade.converged,
                "round_stats": self.cascade.round_stats,
                "total": self.cascade.total,
            },
            "products": [p.to_dict() for p in self.products],
        }

    # -------------------------------------------------- 渲染

    def summary(self) -> str:
        c = self.conditions
        L = []
        L.append("=" * 90)
        L.append("输入")
        L.append("=" * 90)
        for k, v in self.inputs.items():
            L.append(f"  {k}: {v}")
        L.append(f"  条件: {c.describe()}")

        L.append("")
        L.append("=" * 90)
        L.append("① 成分采集")
        L.append("=" * 90)
        for herb, n in self.herb_counts.items():
            L.append(f"  {herb:<12} {n:>4} 个成分")
        L.append(f"  合计 {len(self.compounds)} 个成分（已按 SMILES 去重）")

        L.append("")
        L.append("=" * 90)
        L.append("② 条件激活")
        L.append("=" * 90)
        L.append(f"  激活 {len(self.active_rules)} / {self.n_rules} 条规则")
        for r in self.active_rules[:12]:
            L.append(f"    {r.get('_score', 0):.3f}  {r['name']}")
        if len(self.active_rules) > 12:
            L.append(f"    … 另有 {len(self.active_rules) - 12} 条")

        L.append("")
        L.append("=" * 90)
        L.append("③ 级联")
        L.append("=" * 90)
        L.append(f"  {'轮':>3}{'新增':>7}{'可传播':>8}")
        for st in self.cascade.round_stats:
            L.append(f"  {st['round']:>3}{st['new']:>7}{st['irreversible_new']:>8}")
        main = self.main_products()
        byp = self.byproducts()
        L.append(f"  跑了 {self.cascade.rounds} 轮，"
                 f"收敛：{'是' if self.cascade.converged else '否'}")
        L.append(f"  产物 {self.cascade.total} 个（主体 {len(main)} + 小分子副产物 {len(byp)}）")

        L.append("")
        L.append("=" * 90)
        L.append("④ Top 20 产物（多样性排序 + 按分子式去重）")
        L.append("=" * 90)
        L.append("  ★ 为什么不按分数直接排：实测甘草的纯分数 Top-20 里，")
        L.append("    「羟基氧化」一种规则占了 18 行——不是它最可信，")
        L.append("    而是它作用位点最多（每个仲醇都能氧化）。这样读不出")
        L.append("    「这个方剂会发生哪几类反应」。")
        L.append("    做法：多样性决定【选哪些进来】，分数决定【怎么排】。")
        L.append("    原始分数未被改动，完整清单见 --json 输出。")
        L.append("")
        L.append(f"  {'置信':>6}  {'分子式':<13}{'反应类型':<18}"
                 f"{'来自成分':<22}{'药材':<7}{'轮':>2}{'异构体':>6}")
        L.append("  " + "-" * 88)

        # 多样性负责"选谁进来"，分数负责"怎么排"——
        # 如果按选入顺序显示，分数会忽高忽低，读起来像 bug。
        diverse = sorted(self.diverse_ranking(top=20), key=lambda p: -p.score)
        iso_cnt: Counter = Counter(p.formula for p in self.main_products())
        for p in diverse:
            n_iso = iso_cnt.get(p.formula, 1)
            iso = f"{n_iso}" if n_iso > 1 else ""
            L.append(f"  {p.score:>6.3f}  {p.formula:<13}{p.rule_name:<18}"
                     f"{p.source_name[:20]:<22}{p.source_herb[:5]:<7}"
                     f"{p.round:>2}{iso:>6}")
        n_types = len({p.rule_id for p in diverse})
        L.append(f"  （Top-20 覆盖 {n_types} 种反应类型；"
                 f"主体产物 {len(self.main_products())} 个，"
                 f"按分子式归并后 {len(self.diverse_products())} 个）")

        L.append("")
        L.append("  ── 产物来自哪味药 ──")
        for herb, n in self.by_herb().most_common(8):
            L.append(f"    {herb:<14} {n:>5} 个")

        L.append("")
        L.append("  ── 由哪类反应产生（Top 10）──")
        for rule, n in self.by_rule().most_common(10):
            L.append(f"    {rule:<18} {n:>5} 个")

        L.append("")
        L.append("  ── 小分子副产物（原项目会把这些直接删掉）──")
        for p in byp[:8]:
            L.append(f"    {p.formula:<10} MW {p.mw:>7.1f}  ← {p.rule_name}")
        if len(byp) > 8:
            L.append(f"    … 另有 {len(byp) - 8} 个")

        L.append("")
        L.append(f"（总耗时 {self.elapsed:.1f} 秒）")
        return "\n".join(L)


# ---------------------------------------------------------------- 主入口

def predict(herbs: Optional[Sequence[str]] = None,
            formula_text: Optional[str] = None,
            smiles: Optional[Sequence[str]] = None,
            condition: Any = "煎煮",
            max_per_herb: int = 60,
            max_rounds: int = 8,
            threshold: float = 0.15,
            min_new: int = 10,
            frontier_limit: int = 60,
            max_compounds: int = 150,
            thermo=None,
            engine: Optional[Engine] = None,
            ) -> PredictionResult:
    """一站式预测。三种输入任选其一（可同时给，会合并）。"""

    t0 = time.time()

    if engine is None:
        engine, _rules, _profiles = load_engine()
    else:
        _rules = engine.rules
        _profiles = engine.profiles

    # ---- 条件 ----
    if isinstance(condition, Conditions):
        cond = condition
    elif isinstance(condition, str):
        cond = T.get_template(condition)
    elif isinstance(condition, dict):
        cond = Conditions.from_dict(condition)
    else:
        raise TypeError(f"condition 类型不对: {type(condition)}")

    problems = cond.validate()
    if problems:
        raise ValueError("条件不合法: " + "; ".join(problems))

    # ---- 输入 → 药材列表 ----
    inputs: Dict[str, Any] = {"condition": cond.describe()}
    herb_names: List[str] = []
    dose_info: List[Dict[str, Any]] = []

    if formula_text:
        parsed = parse_formula_text(formula_text)
        herb_names += [p["herb"] for p in parsed if p.get("herb")]
        dose_info = parsed
        inputs["方剂原文"] = formula_text
        inputs["解析出药材"] = [p["herb"] for p in parsed if p.get("herb")]
        inputs["解析器"] = parsed[0].get("_parser") if parsed else "?"
        if dose_info:
            inputs["剂量"] = {p["herb"]: p.get("dose") for p in dose_info
                            if p.get("herb")}

    if herbs:
        herb_names += list(herbs)
        inputs["药材输入"] = list(herbs)

    # 去重保序
    seen = set()
    herb_names = [h for h in herb_names if not (h in seen or seen.add(h))]

    # ---- 成分采集 ----
    compounds: List[Compound] = []
    herb_counts: Dict[str, int] = {}
    missed: List[str] = []

    for h in herb_names:
        cs = compounds_of_herb(h, limit=max_per_herb)
        if not cs:
            # 精确名没命中就试模糊
            hits = list_herbs(h, limit=3)
            if hits:
                cs = compounds_of_herb(hits[0]["name_cn"], limit=max_per_herb)
                if cs:
                    for c in cs:
                        c.herb = hits[0]["name_cn"]
        if cs:
            herb_counts[h] = len(cs)
            compounds.extend(cs)
        else:
            missed.append(h)

    if missed:
        inputs["未匹配到成分的药材"] = missed

    if smiles:
        sm = compounds_from_smiles(list(smiles))
        compounds.extend(sm)
        herb_counts["(直接输入的 SMILES)"] = len(sm)
        inputs["SMILES 输入"] = list(smiles)

    # 跨药材去重（同一成分出现在多味药里只算一次，但保留最先出现的来源）
    uniq: Dict[str, Compound] = {}
    for c in compounds:
        uniq.setdefault(c.smiles, c)
    compounds = list(uniq.values())[:max_compounds]

    if not compounds:
        raise ValueError(
            "没有拿到任何成分。请检查药材名是否正确（数据库里是中文名），"
            "或改用 --smiles 直接给分子。")

    # ---- 条件激活 ----
    act = active_rules(engine.rules, _profiles, cond, threshold)
    active_list = []
    for r, s, _why in act:
        rr = dict(r)
        rr["_score"] = s
        active_list.append(rr)

    # ---- 级联 ----
    res = cascade(engine, compounds, cond,
                  max_rounds=max_rounds, threshold=threshold,
                  min_new=min_new, frontier_limit=frontier_limit,
                  thermo=thermo)

    return PredictionResult(
        inputs=inputs,
        conditions=cond,
        compounds=compounds,
        herb_counts=herb_counts,
        active_rules=active_list,
        cascade=res,
        n_rules=len(_rules),
        elapsed=time.time() - t0,
    )


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(
        description="中药方剂 → 化学反应产物预测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap_dedent("""
            例：
              python predict.py --herbs 附子 干姜 甘草
              python predict.py --formula "甘草2两（炙），干姜1两半，附子1枚（生用）"
              python predict.py --smiles "COC(=O)c1ccccc1" --condition 醇提
              python predict.py --herbs 甘草 --json out.json
        """))
    ap.add_argument("--herbs", nargs="+", help="药材中文名")
    ap.add_argument("--formula", help="方剂原文（含剂量/炮制）")
    ap.add_argument("--smiles", nargs="+", help="直接给分子 SMILES")
    ap.add_argument("--condition", default="煎煮", help="处理条件（模板名）")
    ap.add_argument("--max-per-herb", type=int, default=60)
    ap.add_argument("--max-rounds", type=int, default=8)
    ap.add_argument("--frontier-limit", type=int, default=60)
    ap.add_argument("--json", help="把完整结果写成 JSON")
    ap.add_argument("--list-conditions", action="store_true")
    ap.add_argument("--explain", action="store_true",
                    help="顺便解释哪些反应会发生/不会发生")
    args = ap.parse_args(argv)

    if args.list_conditions:
        print(T.list_templates())
        return 0

    if not (args.herbs or args.formula or args.smiles):
        ap.print_help()
        return 1

    try:
        r = predict(herbs=args.herbs, formula_text=args.formula,
                    smiles=args.smiles, condition=args.condition,
                    max_per_herb=args.max_per_herb,
                    max_rounds=args.max_rounds,
                    frontier_limit=args.frontier_limit)
    except Exception as e:
        print(f"[错误] {e}")
        return 2

    print(r.summary())

    if args.explain:
        engine, rules, profiles = load_engine()
        print()
        print(explain(rules, profiles, r.conditions, show_inactive=10))

    if args.json:
        Path(args.json).write_text(
            json.dumps(r.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n完整结果已写入: {args.json}")

    return 0


def textwrap_dedent(s: str) -> str:
    import textwrap
    return textwrap.dedent(s)


if __name__ == "__main__":
    raise SystemExit(main())
