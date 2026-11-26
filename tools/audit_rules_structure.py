# -*- coding: utf-8 -*-
"""规则结构审计：SMARTS 编译、原子映射守恒、电荷/元素一致性、副产物可解析。

只回答「语法/映射」问题，不判断反应是否化学合理（后者靠测试用例与人工复核）。

用法：
  python -I tools\\audit_rules_structure.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "libs", ROOT / "core"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# 结构审计的严重级别：
#   ERROR = 一定不能放过（编译失败、映射重复/造原子/换元素、副产物坏、逗号 OR+map）
#   INFO  = 规则正常写法（水解/氧化新增的 O、离去基团未映射），只登记不判错
ERROR_KINDS = {
    "PARSE", "TEMPLATES", "DUP_MAP", "ATOM_CREATED", "ELEM_CHANGE",
    "CHARGE_CHANGE", "BAD_BYPRODUCTS", "BAD_CO_REAGENTS",
    "BAD_BYPRODUCTS_N", "BAD_CO_REAGENTS_N", "COMMA_OR_MAPPED",
    "BYPRODUCT_IN_PRODUCT",
}

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdChemReactions  # noqa: E402

RDLogger.DisableLog("rdApp.*")

RULES = ROOT / "rules" / "rules.json"
_FORMULA = re.compile(r"([A-Z][a-z]?)(\d*)")


def parse_formula(s: str):
    out = {}
    for el, n in _FORMULA.findall(s or ""):
        if not el:
            continue
        out[el] = out.get(el, 0) + (int(n) if n else 1)
    return out


def map_atoms(mol):
    """map -> (atomic num, formal charge)；重复 map 单独返回。"""
    d, dup = {}, []
    for a in mol.GetAtoms():
        m = a.GetAtomMapNum()
        if not m:
            continue
        if m in d:
            dup.append(m)
        d[m] = (a.GetAtomicNum(), a.GetFormalCharge())
    return d, dup


def main() -> int:
    rules = json.load(open(RULES, encoding="utf-8"))["rules"]
    issues = []
    counts = Counter()

    for r in rules:
        rid = r.get("id") or "?"
        sm = r.get("smarts") or ""
        st = r.get("status") or "?"
        counts["total"] += 1
        counts["status_" + str(st)] += 1
        try:
            rx = rdChemReactions.ReactionFromSmarts(sm)
        except Exception as ex:
            issues.append((rid, "PARSE", "%s: %s" % (type(ex).__name__, ex)))
            continue
        if rx is None:
            issues.append((rid, "PARSE", "ReactionFromSmarts 返回 None"))
            continue
        nr, np_ = rx.GetNumReactantTemplates(), rx.GetNumProductTemplates()
        if nr == 0 or np_ == 0:
            issues.append((rid, "TEMPLATES", "reactants=%d products=%d" % (nr, np_)))
            continue
        # 合并两侧映射（多反应物时取消 map 重复需先按侧分开）
        side_maps = []
        for i in range(nr):
            m, dup = map_atoms(rx.GetReactantTemplate(i))
            side_maps.append(("R%d" % i, m, dup))
        for i in range(np_):
            m, dup = map_atoms(rx.GetProductTemplate(i))
            side_maps.append(("P%d" % i, m, dup))
        all_maps = {}
        for side, m, dup in side_maps:
            if dup:
                issues.append((rid, "DUP_MAP", "%s 重复 map %s" % (side, sorted(set(dup))[:5])))
            for k, v in m.items():
                all_maps.setdefault(k, {})[side] = v
        for k, sides in sorted(all_maps.items()):
            rvals = [v for s, v in sides.items() if s.startswith("R")]
            pvals = [v for s, v in sides.items() if s.startswith("P")]
            if rvals and not pvals:
                issues.append((rid, "MAP_LOST", "map %d 只在反应物侧" % k))
            elif pvals and not rvals:
                issues.append((rid, "ATOM_CREATED", "map %d 只在产物侧" % k))
            elif rvals and pvals:
                if rvals[0][0] != pvals[0][0]:
                    issues.append((rid, "ELEM_CHANGE", "map %d %s -> %s"
                                   % (k, rvals[0][0], pvals[0][0])))
                if rvals[0][1] != pvals[0][1]:
                    issues.append((rid, "CHARGE_CHANGE", "map %d %d -> %d"
                                   % (k, rvals[0][1], pvals[0][1])))
        if not all_maps:
            issues.append((rid, "NO_MAPS", "SMARTS 没有原子映射"))
        # byproducts / co_reagents 公式可解析
        for key in ("byproducts", "co_reagents"):
            for formula, n in (r.get(key) or {}).items():
                if not parse_formula(formula):
                    issues.append((rid, "BAD_" + key.upper(), repr(formula)))
                try:
                    float(n)
                except Exception:
                    issues.append((rid, "BAD_" + key.upper() + "_N", repr(n)))
        # 副产物同时出现在产物侧（双重计数风险）
        prod_smarts = sm.split(">>", 1)[1] if ">>" in sm else ""
        for formula in (r.get("byproducts") or {}):
            core = formula.rstrip("0123456789")
            if core and core in prod_smarts:
                issues.append((rid, "BYPRODUCT_IN_PRODUCT",
                               "%s 既声明为副产物又出现在产物 SMARTS" % formula))
        # 逗号 OR 原子原语（rdchiral 已知易错）。
        # ★ 只报「没有分号的顶层 OR」，如 [CH1,CH2:3]；
        #   [C;H1,H2:3] / [N;H1,H2:4] 是合法的 AND 属性列表（H1 或 H2），不算错。
        for m in re.finditer(r"\[([^\]]*)\]", sm):
            body = m.group(1)
            if ":" in body and "," in body and ";" not in body:
                issues.append((rid, "COMMA_OR_MAPPED",
                               "顶层逗号 OR + map：%s" % m.group(0)))
                break
        # 产物侧显式 [H] 以外的未映射重原子
        for i in range(np_):
            for a in rx.GetProductTemplate(i).GetAtoms():
                if a.GetAtomicNum() > 1 and a.GetAtomMapNum() == 0:
                    issues.append((rid, "UNMAPPED_PRODUCT_ATOM",
                                   "产物侧有未映射重原子（%s）" % a.GetSymbol()))
                    break

    print("规则 %d 条；状态 %s" % (counts["total"], {k[7:]: v for k, v in counts.items()
                                                     if k.startswith("status_")}))
    errs = [x for x in issues if x[1] in ERROR_KINDS]
    infos = [x for x in issues if x[1] not in ERROR_KINDS]
    print("ERROR %d 条 / INFO %d 条" % (len(errs), len(infos)))
    for title, subset, detail in (("ERROR", errs, True), ("INFO", infos, False)):
        if not subset:
            continue
        print("\n== %s ==" % title)
        by_rule = {}
        for rid, kind, msg in subset:
            by_rule.setdefault(rid, []).append((kind, msg))
        for rid, items in by_rule.items():
            kinds = Counter(k for k, _m in items)
            print("%-42s %s" % (rid, dict(kinds)))
            if detail:
                for kind, msg in items[:10]:
                    print("   [%s] %s" % (kind, msg))
                if len(items) > 10:
                    print("   ... 另有 %d 条" % (len(items) - 10))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
