# -*- coding: utf-8 -*-
"""
chemreact 规则化学合理性检查
============================

★ 为什么需要它（本项目的核心教训之一）

  原子守恒校验是**必要条件，不是充分条件**。
  它挡住的是"漏写原子"和"凭空造原子"，
  但挡不住「产物结构本身就是错的」——因为任何原子缺口都能靠
  【编一个副产物】填平。

  真实案例（都发生在本项目里）：
    · 「分子内脱水成醚」产物写成 [O:1]1[...][O:5]1 → 含 O-O 键，成了 1,2-二氧戊环。
      它之所以通过原子守恒校验，是因为推导器给它配了 byproducts={'H2':1}。
      数字对上了，化学是错的。
    · 「分子内半缩醛化」把醛基的氧写进环又让它当羟基，化学上说不通。

  本模块补的就是这道闸门：**不看原子数，看结构合不合理。**

检查项
------
  1. 过氧键 O-O      —— 极罕见，绝大多数规则都不该产生
  2. 新生成的三元环   —— 除环氧化物/氮丙啶外基本不合理
  3. 电荷不守恒      —— 产物净电荷 ≠ 反应物净电荷
  4. 副产物是否合乎反应类型
  5. 陪跑试剂是否合乎反应类型
  6. 产物价态是否合法（sanitize）

用法
----
    python sanity.py                       # 全库体检
    python sanity.py --rules xxx.json
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "rules", _STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

from schema import load_rules, _load_substrates, atom_counts, formula_atoms

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")


# ---------------------------------------------------------------- 判据

# 过氧键：O-O 单键。用一个 SMARTS 足以表达。
PEROXIDE_SMARTS = Chem.MolFromSmarts("[#8]-[#8]")

# 三元环里出现这些元素才考虑放行（环氧化物、氮丙啶、环丙烷）
RING3_TOLERATED = {"C", "N", "O"}

# 各反应类型「合理」的副产物。不在表里的副产物会被 flag。
PLAUSIBLE_BYPRODUCTS = {
    "hydrolysis":     {"H2O"},
    "condensation":   {"H2O"},
    "esterification": {"H2O"},
    "cyclization":    {"H2O", "H2"},
    "elimination":    {"H2O", "NH3", "H2"},
    "decarboxylation": {"CO2", "H2O"},
    "oxidation":      {"H2O", "H2O2"},
    "reduction":      {"H2O"},
    "hydroxylation":  {"H2O"},
    "hydration":      set(),
    "rearrangement":  set(),
    "addition":       set(),
    "demethylation":  set(),
    "esterification_": set(),
}

# 各反应类型「合理」的陪跑试剂
PLAUSIBLE_COREAGENTS = {
    "hydrolysis":      {"H2O"},
    "hydration":       {"H2O"},
    "oxidation":       {"O2", "H2O2"},
    "reduction":       {"H2", "NADH"},
    "demethylation":   {"H2O"},
    "hydroxylation":   {"O2", "H2O2"},
    "elimination":     {"O2"},
    "condensation":    {"O2"},
    "cyclization":     set(),
    "rearrangement":   set(),
    "decarboxylation": set(),
    "addition":        set(),
    "esterification":  set(),
}


@dataclass
class Issue:
    rule_id: str
    rule_name: str
    severity: str          # "error" | "warn"
    kind: str
    detail: str
    example: str = ""


# ---------------------------------------------------------------- 结构检查

def _ring_sizes(mol: Chem.Mol) -> List[frozenset]:
    ri = mol.GetRingInfo()
    return [frozenset(r) for r in ri.AtomRings()]


def check_product_structure(product_smiles: str,
                            substrate_smiles: str) -> List[Tuple[str, str]]:
    """单个产物的结构合理性。返回 [(kind, detail)]。"""
    out: List[Tuple[str, str]] = []
    pm = Chem.MolFromSmiles(product_smiles)
    sm = Chem.MolFromSmiles(substrate_smiles)
    if pm is None:
        return [("价态非法", "产物无法解析为分子")]

    # ---- 1. 过氧键 ----
    if PEROXIDE_SMARTS is not None and pm.HasSubstructMatch(PEROXIDE_SMARTS):
        had = (sm is not None and sm.HasSubstructMatch(PEROXIDE_SMARTS))
        if not had:
            out.append(("过氧键 O-O",
                        "产物含新生成的 O-O 单键——极罕见，多半是 SMARTS 写错"))

    # ---- 2. 新生成的三元环 ----
    sub_rings = _ring_sizes(sm) if sm is not None else []
    for ring in _ring_sizes(pm):
        if len(ring) == 3 and not any(r == ring for r in sub_rings):
            syms = sorted(pm.GetAtomWithIdx(i).GetSymbol() for i in ring)
            if syms.count("O") >= 2:
                out.append(("含双氧三元环",
                            f"新生成三元环 {syms}——两个氧在一个三元环里，几乎必然不合理"))

    # ---- 3. 电荷 ----
    if sm is not None:
        qp = Chem.GetFormalCharge(pm)
        qs = Chem.GetFormalCharge(sm)
        if qp != qs:
            out.append(("电荷不守恒",
                        f"产物净电荷 {qp:+d}，底物 {qs:+d}"))

    return out


# ---------------------------------------------------------------- 试剂/副产物

def check_byproducts(rule: Dict[str, Any]) -> List[Tuple[str, str]]:
    """副产物是否合乎反应类型。"""
    out: List[Tuple[str, str]] = []
    by = rule.get("byproducts") or {}
    cat = rule.get("category", "")
    allowed = PLAUSIBLE_BYPRODUCTS.get(cat)

    for formula in by:
        # 氧气/氢气作为副产物几乎从不合理
        if formula in ("O2", "O3"):
            out.append(("副产物不合理",
                        f"{cat} 类反应产出 {formula}——副产物是氧气几乎不可能，"
                        f"多半是把「消耗氧」写反了"))
        # 产氢气只有脱氢/环化类才合理
        if formula == "H2" and cat not in ("cyclization", "elimination",
                                           "rearrangement", "oxidation"):
            out.append(("副产物可疑",
                        f"{cat} 类反应产出 H2——"
                        f"★这是「编一个副产物把原子数凑平」的典型症状★，"
                        f"请人工确认产物结构是否本来就错了"))
        if allowed is not None and formula not in allowed:
            out.append(("副产物类型不符",
                        f"{cat} 类反应通常的副产物是 {sorted(allowed) or '无'}，"
                        f"但这里写了 {formula}"))

    return out


def check_coreagents(rule: Dict[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    co = rule.get("co_reagents") or {}
    cat = rule.get("category", "")
    allowed = PLAUSIBLE_COREAGENTS.get(cat)

    for formula in co:
        if formula in ("O2", "O3") and cat not in ("oxidation", "hydroxylation",
                                                   "elimination", "condensation"):
            out.append(("陪跑试剂可疑",
                        f"{cat} 类反应消耗 {formula}——不是不可能，但需确认"))
        if formula == "H2" and cat != "reduction":
            out.append(("陪跑试剂可疑",
                        f"{cat} 类反应消耗 H2——通常只有还原类才需要氢"))
        if allowed is not None and formula not in allowed:
            out.append(("陪跑试剂类型不符",
                        f"{cat} 类反应通常消耗 {sorted(allowed) or '无'}，但这里写了 {formula}"))
    return out


# ---------------------------------------------------------------- 综合

def audit_rule(rule: Dict[str, Any], substrates,
               max_sub: int = 80, max_examples: int = 2) -> List[Issue]:
    issues: List[Issue] = []
    rid, rname = rule["id"], rule["name"]

    def add(sev, kind, detail, example=""):
        issues.append(Issue(rid, rname, sev, kind, detail, example))

    # 规则层面的检查（不用跑反应）
    for kind, detail in check_byproducts(rule):
        add("warn", kind, detail)
    for kind, detail in check_coreagents(rule):
        add("warn", kind, detail)

    # 结构层面的检查（要跑反应）
    smarts = rule.get("smarts")
    n_react = 1
    try:
        rxn_rd = AllChem.ReactionFromSmarts(smarts)
    except Exception as e:
        add("error", "SMARTS 编译失败", str(e))
        return issues
    if rxn_rd is None:
        add("error", "SMARTS 编译失败", "返回 None")
        return issues
    n_react = rxn_rd.GetNumReactantTemplates()

    pool = rule.get("co_substrate_pool") or []
    co_mols = []
    for item in pool[:2]:
        smi = item.get("smiles") if isinstance(item, dict) else None
        if smi:
            m = Chem.MolFromSmiles(smi)
            if m is not None:
                co_mols.append(m)

    found: Dict[str, int] = {}
    n_checked = 0

    for name, smiles, mol in substrates:
        if n_checked >= max_sub:
            break
        if len(Chem.GetMolFrags(mol)) > 1:
            continue

        outcomes: List[str] = []
        try:
            if n_react == 1:
                for ps in rxn_rd.RunReactants((mol,))[:3]:
                    frags = []
                    ok = True
                    for p in ps:
                        pc = Chem.Mol(p)
                        try:
                            Chem.SanitizeMol(pc)
                        except Exception:
                            ok = False
                            break
                        frags.append(Chem.MolToSmiles(pc))
                    if ok and frags:
                        outcomes.append(".".join(frags))
            else:
                for co in co_mols:
                    for ps in rxn_rd.RunReactants((mol, co))[:3]:
                        frags = []
                        ok = True
                        for p in ps:
                            pc = Chem.Mol(p)
                            try:
                                Chem.SanitizeMol(pc)
                            except Exception:
                                ok = False
                                break
                            frags.append(Chem.MolToSmiles(pc))
                        if ok and frags:
                            outcomes.append(".".join(frags))
                    if outcomes:
                        break
        except Exception:
            continue

        if outcomes:
            n_checked += 1

        for out in outcomes:
            for part in out.split("."):
                for kind, detail in check_product_structure(part, smiles):
                    key = kind
                    found[key] = found.get(key, 0) + 1
                    if found[key] <= max_examples:
                        add("error" if "过氧" in kind or "三元环" in kind else "warn",
                            kind, detail,
                            example=f"{name or smiles[:26]} → {part[:40]}")

    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="规则化学合理性检查")
    ap.add_argument("--rules", default=str(_HERE / "rules.json"))
    ap.add_argument("--db", default=r"D:\TCMAI\tcm.db")
    ap.add_argument("--limit", type=int, default=800)
    ap.add_argument("--report", default=None)
    args = ap.parse_args(argv)

    profiles, rules = load_rules(args.rules)
    substrates = _load_substrates(args.db, args.limit)
    print(f"规则 {len(rules)} 条 | 底物 {len(substrates)} 个\n")

    all_issues: List[Issue] = []
    for r in rules:
        if r.get("status") == "disabled":
            continue
        all_issues.extend(audit_rule(r, substrates))

    errors = [i for i in all_issues if i.severity == "error"]
    warns = [i for i in all_issues if i.severity == "warn"]

    if errors:
        print("=" * 92)
        print(f"★ 结构性问题 {len(errors)} 条（校验器抓不到，必须人工确认）★")
        print("=" * 92)
        for i in errors:
            print(f"  [{i.rule_name}] {i.kind}: {i.detail}")
            if i.example:
                print(f"       例：{i.example}")

    if warns:
        print()
        print("=" * 92)
        print(f"⚠ 需要确认 {len(warns)} 条")
        print("=" * 92)
        for i in warns:
            print(f"  [{i.rule_name}] {i.kind}: {i.detail}")

    if not all_issues:
        print("✓ 未发现化学合理性问题")

    print()
    print(f"汇总：结构性问题 {len(errors)} | 待确认 {len(warns)}")

    if args.report:
        lines = ["# 规则化学合理性检查报告\n",
                 f"- 规则总数：{len(rules)}",
                 f"- 结构性问题：**{len(errors)}**",
                 f"- 待确认：{len(warns)}\n",
                 "## 结构性问题\n"]
        for i in errors:
            lines.append(f"- **[{i.rule_name}] {i.kind}**：{i.detail}")
            if i.example:
                lines.append(f"  - 例：`{i.example}`")
        lines.append("\n## 待确认\n")
        for i in warns:
            lines.append(f"- [{i.rule_name}] {i.kind}：{i.detail}")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"报告已写入: {args.report}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
