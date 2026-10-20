# -*- coding: utf-8 -*-
"""
chemreact 规则校验器
====================

这是规则库的闸门。任何一条规则想进 rules.json，必须先过这里。

校验分两层：

  第一层 静态检查（不需要底物）
    - 必填字段齐不齐
    - SMARTS 能不能被 RDKit 编译
    - co_reagents / byproducts 的分子式写得对不对
    - conditions 或 condition_profile 能不能解析出完整条件窗口
    - priority / category / status 取值是否合法

  第二层 实证检查（需要真实底物，这是关键）
    - 拿 N 个真实分子去跑这条规则
    - 对每一个产物集合，检验：
          原子(底物) + 原子(co_reagents)  ==  原子(所有SMARTS产物) + 原子(byproducts)
    - 统计配平率；只要有失衡就报出来，并给出"差在哪几个原子"
    - 如果一条规则在所有底物上都产不出东西 → 判定为死规则

第二层的存在理由：静态看 SMARTS 是看不出原子不守恒的。
本项目原来的 23 条规则，看代码全都"像是对的"，
但实测 21 条不配平、3 条是真错误。只有跑真实数据才暴露得出来。

设计原则：
  - 不依赖 D:\\TCMAI 的任何 .py 文件（只读它的数据库）
  - 不修改任何东西，纯函数
  - 缺东西时报告问题，不抛异常打断整个批次

用法：
    from schema import load_rules, validate_rule
    profiles, rules = load_rules("rules/rules.json")
    report = validate_rule(rules[0], profiles, substrates)
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

# 校验器自己安静点，别被 RDKit 的警告刷屏
RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

# ---------------------------------------------------------------- 常量

REQUIRED_RULE_KEYS = ("id", "name", "category", "smarts", "reversible")
REQUIRED_CONDITION_KEYS = ("temperature", "pH", "solvent", "catalyst", "time_min")

VALID_CATEGORIES = {
    "hydrolysis", "oxidation", "reduction", "elimination", "demethylation",
    "decarboxylation", "hydroxylation", "hydration", "rearrangement",
    "esterification", "condensation", "substitution", "addition",
    "cyclization", "protection", "deprotection", "coupling", "acid_base",
}

# status 语义：
#   active                  正常启用
#   draft                   草稿：新写的规则，co_reagents 还没推导/校验，不进产物预测
#   fixed_pending_verify    改过 SMARTS，等校验器确认
#   verify                  有疑点，需人工复核
#   risky                   能跑但产物质量差，建议降权或重写
#   disabled                已知坏规则，停用
VALID_STATUS = {"active", "draft", "fixed_pending_verify", "verify", "risky",
                "disabled"}

_FORMULA_RE = re.compile(r"([A-Z][a-z]?)(\d*)")


# ---------------------------------------------------------------- 分子式 / 原子计数

def parse_formula(formula: str) -> Dict[str, float]:
    """把 'H2O' / 'O2' / 'C7H6O2' 解析成 {'H':2.0,'O':1.0}。

    写错就抛 ValueError —— 宁可在校验期炸，也别让它悄悄污染配平计算。
    """
    if not isinstance(formula, str) or not formula:
        raise ValueError(f"分子式必须是非空字符串，收到 {formula!r}")
    counts: Dict[str, float] = {}
    pos = 0
    for m in _FORMULA_RE.finditer(formula):
        if m.start() != pos:
            raise ValueError(f"无法解析的分子式片段: {formula!r} 在位置 {pos}")
        element, digits = m.group(1), m.group(2)
        counts[element] = counts.get(element, 0.0) + (float(digits) if digits else 1.0)
        pos = m.end()
    if pos != len(formula):
        raise ValueError(f"无法解析的分子式: {formula!r}")
    return counts


def formula_atoms(spec: Optional[Dict[str, float]], subject: str) -> Dict[str, float]:
    """把 {'H2O': 1, 'O2': 0.5} 这种配平系数表累加成总原子数。"""
    total: Dict[str, float] = {}
    if not spec:
        return total
    if not isinstance(spec, dict):
        raise ValueError(f"{subject} 必须是 {{分子式: 系数}} 形式，收到 {type(spec).__name__}")
    for formula, coeff in spec.items():
        if not isinstance(coeff, (int, float)) or coeff < 0:
            raise ValueError(f"{subject} 里 {formula} 的系数必须是非负数，收到 {coeff!r}")
        for el, n in parse_formula(formula).items():
            total[el] = total.get(el, 0.0) + n * float(coeff)
    return total


def atom_counts(mol: Chem.Mol) -> Dict[str, float]:
    """数一个分子的原子数，氢按隐式氢算（GetTotalNumHs）。

    注意：调用前分子必须已经 sanitize 过，否则隐式氢数是错的。
    """
    counts: Dict[str, float] = {}
    for atom in mol.GetAtoms():
        sym = atom.GetSymbol()
        counts[sym] = counts.get(sym, 0.0) + 1.0
        h = atom.GetTotalNumHs()
        if h:
            counts["H"] = counts.get("H", 0.0) + float(h)
    return counts


def add_atoms(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    out = dict(a)
    for el, n in b.items():
        out[el] = out.get(el, 0.0) + n
    return out


def atoms_equal(a: Dict[str, float], b: Dict[str, float], tol: float = 1e-6) -> bool:
    return not atom_diff(a, b, tol)


def atom_diff(left: Dict[str, float], right: Dict[str, float], tol: float = 1e-6
              ) -> Dict[str, float]:
    """返回 right - left 的非零项（保留一位小数便于阅读）。"""
    out: Dict[str, float] = {}
    for el in sorted(set(left) | set(right)):
        d = right.get(el, 0.0) - left.get(el, 0.0)
        if abs(d) > tol:
            out[el] = round(d, 4)
    return out


def format_atoms(counts: Dict[str, float]) -> str:
    return "".join(f"{el}{counts[el]:g}" for el in sorted(counts) if counts[el])


# ---------------------------------------------------------------- 加载

def load_rules(path: str | Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """读 rules.json，返回 (profiles, rules)。会检查 id 是否重复。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
    rules = data.get("rules", [])
    seen = set()
    for r in rules:
        rid = r.get("id")
        if rid in seen:
            raise ValueError(f"规则 id 重复: {rid}")
        seen.add(rid)
    return profiles, rules


def resolve_conditions(rule: Dict[str, Any], profiles: Dict[str, Any]
                       ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """把 condition_profile 展开成完整 conditions。规则里显式写的字段优先。"""
    problems: List[str] = []
    base: Dict[str, Any] = {}

    profile_name = rule.get("condition_profile")
    if profile_name:
        if profile_name not in profiles:
            problems.append(f"condition_profile 不存在: {profile_name!r}")
        else:
            base = dict(profiles[profile_name])

    if isinstance(rule.get("conditions"), dict):
        for k, v in rule["conditions"].items():
            base[k] = v

    if not base:
        problems.append("既没有 condition_profile，也没有 conditions")
        return None, problems

    for key in REQUIRED_CONDITION_KEYS:
        if key not in base:
            problems.append(f"条件窗口缺少 {key!r}")

    for key in ("temperature", "pH", "time_min"):
        spec = base.get(key)
        if spec is None:
            continue
        if not isinstance(spec, dict) or "min" not in spec or "max" not in spec:
            problems.append(f"{key} 必须是 {{min, max, default?}}，收到 {spec!r}")
            continue
        if spec["min"] > spec["max"]:
            problems.append(f"{key} 的 min({spec['min']}) > max({spec['max']})")
        d = spec.get("default")
        if d is not None and not (spec["min"] <= d <= spec["max"]):
            problems.append(f"{key} 的 default({d}) 不在 [{spec['min']}, {spec['max']}] 内")

    for key in ("solvent", "catalyst", "atmosphere"):
        v = base.get(key)
        if v is not None and not isinstance(v, list):
            problems.append(f"{key} 必须是列表，收到 {type(v).__name__}")

    return base, problems


# ---------------------------------------------------------------- 静态检查

def _check_atom_maps(rxn) -> List[str]:
    """检查原子映射编号的一致性。

    这条检查来自一次真实踩坑：产物侧出现了一个反应物侧不存在的映射编号
    （比如新增的氧写成 [O:5]），
      · rdkit 的 RunReactants 会静默容忍，甚至凑出一个"数值上配平"的结果；
      · RDChiral 会在 rdchiralRun 里抛 KeyError，而且只在特定底物上才触发，
        极难定位。
    正确写法：新增的原子【一律不编号】，例如 [OH]、[O]，而不是 [O:5]。

    另一类隐患也一并报出：同一个编号在反应物与产物里指向不同元素
    （例如反应物 [N:3]、产物 [O:3]），说明映射写串了。
    """
    problems: List[str] = []

    rt_maps: Dict[int, str] = {}
    for i in range(rxn.GetNumReactantTemplates()):
        for a in rxn.GetReactantTemplate(i).GetAtoms():
            n = a.GetAtomMapNum()
            if n:
                rt_maps[n] = a.GetSymbol()

    pt_maps: Dict[int, str] = {}
    for i in range(rxn.GetNumProductTemplates()):
        for a in rxn.GetProductTemplate(i).GetAtoms():
            n = a.GetAtomMapNum()
            if n:
                pt_maps.setdefault(n, a.GetSymbol())

    orphan = sorted(set(pt_maps) - set(rt_maps))
    if orphan:
        detail = ", ".join(f"[{pt_maps[n]}:{n}]" for n in orphan)
        problems.append(
            f"产物侧的原子映射编号 {orphan} ({detail}) 在反应物侧不存在 —— "
            f"新增原子必须不编号（写 [OH] 而不是 [O:5]），"
            f"否则 RDChiral 会抛 KeyError"
        )

    swapped = [(n, rt_maps[n], pt_maps[n])
               for n in sorted(set(rt_maps) & set(pt_maps))
               if rt_maps[n] != pt_maps[n]]
    for n, rsym, psym in swapped:
        problems.append(
            f"原子映射编号 {n} 在反应物里是 {rsym}、在产物里却变成 {psym} —— "
            f"映射写串了，rdkit 会照做（把原子改成别的元素），必须修正"
        )

    return problems


def static_checks(rule: Dict[str, Any], profiles: Dict[str, Any]) -> List[str]:
    problems: List[str] = []

    for key in REQUIRED_RULE_KEYS:
        if key not in rule or rule[key] in (None, ""):
            problems.append(f"缺少必填字段 {key!r}")

    rid = rule.get("id", "<无 id>")

    if rule.get("category") not in VALID_CATEGORIES:
        problems.append(f"category {rule.get('category')!r} 不在允许集合内")

    if not isinstance(rule.get("reversible"), bool):
        problems.append("reversible 必须是布尔值")

    prio = rule.get("priority")
    if prio is not None and (not isinstance(prio, (int, float)) or not 0.0 <= prio <= 1.0):
        problems.append(f"priority 必须在 [0,1]，收到 {prio!r}")

    status = rule.get("status")
    if status is not None and status not in VALID_STATUS:
        problems.append(f"status {status!r} 不在允许集合内")

    lim = rule.get("max_products_per_molecule")
    if lim is not None:
        if not isinstance(lim, int) or isinstance(lim, bool) or lim < 1:
            problems.append(f"max_products_per_molecule 必须是正整数，收到 {lim!r}")

    smarts = rule.get("smarts")
    if isinstance(smarts, str) and smarts:
        if ">>" not in smarts:
            problems.append("SMARTS 缺少 '>>'，不是一条反应式")
        else:
            try:
                rxn = AllChem.ReactionFromSmarts(smarts)
                if rxn is None:
                    problems.append("SMARTS 编译返回 None")
                else:
                    n_react = rxn.GetNumReactantTemplates()
                    if n_react not in (1, 2):
                        problems.append(
                            f"只支持 1 个或 2 个反应物模板，这条有 {n_react} 个"
                        )
                    elif n_react == 2:
                        # 双反应物规则必须声明"第二个反应物从哪来"。
                        # 引擎会把它和底物配对，配对的候选由条件决定
                        # （醇提时池子里才有乙醇）。
                        pool = rule.get("co_substrate_pool")
                        if not isinstance(pool, list) or not pool:
                            problems.append(
                                "双反应物规则必须声明 co_substrate_pool"
                                "（第二个反应物的候选池）"
                            )
                        else:
                            for i, item in enumerate(pool):
                                if not isinstance(item, dict) or not item.get("smiles"):
                                    problems.append(
                                        f"co_substrate_pool[{i}] 必须是 "
                                        f'{{"smiles": ..., "name": ...}} 形式'
                                    )
                    problems.extend(_check_atom_maps(rxn))
            except Exception as e:
                problems.append(f"SMARTS 编译失败: {e}")

    for key in ("co_reagents", "byproducts"):
        try:
            formula_atoms(rule.get(key), key)
        except ValueError as e:
            problems.append(str(e))

    _, cond_problems = resolve_conditions(rule, profiles)
    problems.extend(cond_problems)

    return problems


# ---------------------------------------------------------------- 实证检查

def _rdchiral_outcomes(smarts: str, smiles: str, max_outcomes: int) -> List[str]:
    """用 RDChiral 跑一条规则，返回产物 SMILES 列表（可能是 '.' 连接的多组分）。

    RDChiral 与 rdkit 原生 RunReactants 的关键差别：
    它在处理"环内断键"时会把环正确打开成一条链，而不是复制环上的原子。
    """
    from rdchiral.main import rdchiralRun, rdchiralReaction, rdchiralReactants

    rxn = rdchiralReaction(smarts)
    reactants = rdchiralReactants(smiles)
    out = rdchiralRun(rxn, reactants) or []
    return list(out)[:max_outcomes]


def empirical_balance(rule: Dict[str, Any],
                      substrates: Sequence[Tuple[str, str, Chem.Mol]],
                      max_substrates: int = 400,
                      max_product_sets_per_substrate: int = 5,
                      max_examples: int = 3,
                      engine: str = "rdkit") -> Dict[str, Any]:
    """用真实底物检验原子守恒。

    substrates: [(名称, SMILES, RDKit Mol), ...]
    engine:     "rdkit" | "rdchiral"
    """
    result: Dict[str, Any] = {
        "engine": engine,
        "matched_substrates": 0,
        "product_sets_checked": 0,
        "balanced": 0,
        "unbalanced": 0,
        "atom_loss": 0,
        "atom_creation": 0,
        "sanitize_failures": 0,
        "skipped_multifragment": 0,
        "probe_matched": 0,
        "probe_balanced": 0,
        "probe_unbalanced": 0,
        "no_products_at_all": False,
        "examples": [],
        "error": None,
    }

    try:
        co_atoms = formula_atoms(rule.get("co_reagents"), "co_reagents")
        by_atoms = formula_atoms(rule.get("byproducts"), "byproducts")
    except ValueError as e:
        result["error"] = str(e)
        return result

    rxn = None
    try:
        # 无论用哪个引擎都先编译 rdkit 反应式——
        # 因为要靠它读「有几个反应物模板」来决定走哪条路。
        rxn = AllChem.ReactionFromSmarts(rule["smarts"])
    except Exception as e:
        result["error"] = f"SMARTS 编译失败: {e}"
        return result

    if rxn is None:
        result["error"] = "SMARTS 编译返回 None"
        return result

    n_react_templates = rxn.GetNumReactantTemplates()
    if n_react_templates == 2:
        engine = "rdkit"          # 双反应物只能用 rdkit 原生
        result["engine"] = "rdkit (双反应物)"
    elif engine == "rdchiral":
        try:
            import rdchiral  # noqa: F401
        except Exception as e:
            result["error"] = f"rdchiral 不可用: {e}"
            return result
    elif engine != "rdkit":
        result["error"] = f"未知 engine: {engine!r}"
        return result

    produced_anything = False
    co_per_group: List[Tuple[Dict[str, float], Any]] = []

    # ★ 把「人工指定底物」追加进来。
    #   动机：tcm.db 里没有某些类型的分子（β-二羰基酸、肉桂酸型、γ-氨基丁酸型…），
    #   校验器在真实底物上跑就只能报 NO_SUBSTRATE——这个结论既不能证实也不能证伪，
    #   很容易被误读成"规则坏了"。本项目已经因此误判过三次。
    #   规则可以声明 probe_substrates（化学上必定能匹配的底物），据此补验。
    all_subs: List[Tuple[str, str, Any, bool]] = [
        (n, s, m, False) for (n, s, m) in substrates
    ]
    for p in (rule.get("probe_substrates") or []):
        smi = p.get("smiles") if isinstance(p, dict) else None
        if not smi:
            continue
        pm = Chem.MolFromSmiles(smi)
        if pm is None:
            continue
        all_subs.append((f"[人工底物]{p.get('name', '')}", smi, pm, True))

    n_db_matched = 0

    for name, smiles, mol, is_probe in all_subs:
        # 数据库底物跑够 max_substrates 个就停；人工底物不受这个上限限制
        if not is_probe and n_db_matched >= max_substrates:
            continue
        # 多片段底物（SMILES 里带 '.'，即盐 / 混合物 / 多组分体系）必须跳过。
        # 原因：反应只作用于其中一个片段，而底物侧的原子数若按整分子算，
        #      会得出"产物比底物少一大截"的假失衡。这是校验方法本身的坑，
        #      不是规则的错 —— 实测中它制造了大量假阳性。
        if len(Chem.GetMolFrags(mol)) > 1:
            result["skipped_multifragment"] += 1
            continue

        product_groups: List[List[Chem.Mol]] = []

        # ★ 双反应物规则走 rdkit 原生引擎。
        #   rdchiral 的 rdchiralRun 里写死了 RunReactants((mol,)) ——
        #   单元素元组，不支持多反应物。
        #   这类规则（酯交换、席夫碱、酯化…）断的通常是非环键，
        #   所以配合 !@ 约束用 rdkit 原生是可行的折中。
        n_react = rxn.GetNumReactantTemplates()

        if n_react == 2:
            pool = rule.get("co_substrate_pool") or []
            for item in pool:
                co_smi = item.get("smiles") if isinstance(item, dict) else str(item)
                co_mol = Chem.MolFromSmiles(co_smi) if co_smi else None
                if co_mol is None:
                    continue
                try:
                    Chem.SanitizeMol(co_mol)
                except Exception:
                    continue
                try:
                    res = rxn.RunReactants((mol, co_mol))
                except Exception:
                    continue
                for pset in res[:max_product_sets_per_substrate]:
                    prods = [Chem.Mol(p) for p in pset]
                    # 左侧要把第二个反应物也算进去
                    product_groups.append(prods)
                    co_atoms_of_this = atom_counts(co_mol)
                    co_per_group.append((co_atoms_of_this, item))
                if product_groups:
                    break        # 池子里第一个能反应的分子就够了
        elif engine == "rdkit":
            try:
                res = rxn.RunReactants((mol,))
            except Exception as e:
                result["error"] = f"RunReactants 抛异常（底物 {name}）: {e}"
                return result
            for pset in res[:max_product_sets_per_substrate]:
                product_groups.append([Chem.Mol(p) for p in pset])
                co_per_group.append(({}, None))
        else:
            try:
                outcomes = _rdchiral_outcomes(rule["smarts"], smiles,
                                              max_product_sets_per_substrate)
            except Exception as e:
                result["error"] = f"rdchiralRun 抛异常（底物 {name}）: {e}"
                return result
            for smi in outcomes:
                pm = Chem.MolFromSmiles(smi)
                if pm is not None:
                    product_groups.append([pm])
                    co_per_group.append(({}, None))

        if not product_groups:
            continue

        result["matched_substrates"] += 1
        if is_probe:
            result["probe_matched"] += 1
        else:
            n_db_matched += 1

        for group, (co_extra, _item) in zip(product_groups, co_per_group):
            left = add_atoms(add_atoms(atom_counts(mol), co_atoms), co_extra)
            right = dict(by_atoms)
            ok = True
            for p in group:
                try:
                    Chem.SanitizeMol(p)
                except Exception:
                    ok = False
                    break
                right = add_atoms(right, atom_counts(p))

            if not ok:
                result["sanitize_failures"] += 1
                continue

            produced_anything = True
            result["product_sets_checked"] += 1

            diff = atom_diff(left, right)
            if not diff:
                result["balanced"] += 1
                if is_probe:
                    result["probe_balanced"] += 1
            else:
                result["unbalanced"] += 1
                if is_probe:
                    result["probe_unbalanced"] += 1
                # 区分两种性质完全不同的失衡：
                #   atom_loss     产物比底物少原子 → 漏写了产物片段（如 CO2 没写），补上即可
                #   atom_creation 产物比底物多原子 → SMARTS 产物模板写坏，RDKit 复制了原子，
                #                 必须换引擎或重写规则，不是补一个分子式能解决的
                if sum(right.values()) > sum(left.values()):
                    result["atom_creation"] += 1
                    kind = "凭空造原子"
                else:
                    result["atom_loss"] += 1
                    kind = "漏写产物片段"
                if len(result["examples"]) < max_examples:
                    result["examples"].append({
                        "substrate": name or smiles[:40],
                        "kind": kind,
                        "diff_right_minus_left": diff,
                    })

        if result["matched_substrates"] >= max_substrates:
            break

    result["no_products_at_all"] = (result["matched_substrates"] > 0
                                    and not produced_anything)

    # 「产物泛滥度」：平均每个底物产出多少个产物。
    # 这个指标治的是一种配平完全正确、但化学上没用的规则：
    # 比如"给任意芳环任意位置加羟基"，配平 100% 通过，
    # 但 400 个底物能吐出 1895 个产物，等于没说。
    # 原 tcm_analyzer.py 里有个 RULE_LIMITS 就是在治这个病，这里把它量化。
    if result["matched_substrates"]:
        result["products_per_molecule"] = round(
            result["product_sets_checked"] / result["matched_substrates"], 2)
    else:
        result["products_per_molecule"] = 0.0

    return result


# ---------------------------------------------------------------- 综合校验

def validate_rule(rule: Dict[str, Any],
                  profiles: Dict[str, Any],
                  substrates: Optional[Sequence[Tuple[str, str, Chem.Mol]]] = None,
                  **balance_kwargs) -> Dict[str, Any]:
    """一条规则的完整体检报告。

    返回 dict:
      id, name, status, static_problems[], balance{}, verdict, ok
    verdict 取值：
      PASS            静态 + 实证全过
      STATIC_FAIL     静态检查没过（SMARTS 编译失败之类）
      DEAD_RULE       能编译、能匹配底物，但产不出任何产物
      ATOM_CREATION   产物原子数 > 底物原子数，SMARTS 模板写坏，必须重写规则
      UNBALANCED      产物原子数 < 底物原子数，漏写了产物片段（如 CO2）
      NO_SUBSTRATE    静态通过，数据库样本里没有底物匹配，且规则也没提供人工底物
                      —— 注意：这只说明【无法证伪】，不等于规则是错的
      PASS_PROBE      数据库样本覆盖不到，但【人工指定底物】跑通了
    """
    static_problems = static_checks(rule, profiles)

    report: Dict[str, Any] = {
        "id": rule.get("id"),
        "name": rule.get("name"),
        "status": rule.get("status"),
        "engine": balance_kwargs.get("engine", "rdkit"),
        "static_problems": static_problems,
        "balance": None,
        "verdict": None,
        "ok": False,
    }

    if static_problems:
        report["verdict"] = "STATIC_FAIL"
        return report

    if substrates is None:
        report["verdict"] = "NO_SAMPLE"
        report["ok"] = True
        return report

    bal = empirical_balance(rule, substrates, **balance_kwargs)
    report["balance"] = bal

    if bal["error"]:
        report["verdict"] = "STATIC_FAIL"
        return report

    if bal["no_products_at_all"]:
        report["verdict"] = "DEAD_RULE"
        return report

    if bal["matched_substrates"] == 0:
        report["verdict"] = "NO_SUBSTRATE"
        report["ok"] = True
        return report

    if bal["product_sets_checked"] == 0:
        report["verdict"] = "DEAD_RULE"
        return report

    # 先判"凭空造原子"——这是 SMARTS 模板的结构性缺陷，比漏写片段严重
    if bal["atom_creation"] > 0:
        report["verdict"] = "ATOM_CREATION"
        return report

    if bal["unbalanced"] > 0:
        report["verdict"] = "UNBALANCED"
        return report

    # ★ 数据库样本跑通了，但一个都没匹配上，全靠人工底物验证
    #   → 单列一个 verdict，提醒"这条规则的置信度来自人工底物，不是大规模抽样"
    if bal["probe_matched"] > 0 and bal["matched_substrates"] == bal["probe_matched"]:
        report["verdict"] = "PASS_PROBE"
        report["ok"] = True
        return report

    report["verdict"] = "PASS"
    report["ok"] = True
    return report


# ---------------------------------------------------------------- CLI

def _load_substrates(db_path: str, limit: int = 4000
                     ) -> List[Tuple[str, str, Chem.Mol]]:
    """从 tcm.db 只读取一批带 SMILES 的成分。只读，不写。

    ★ 优先用 isomeric_smiles ★
    compounds 表 31646 行里，19043 行（60%）的 isomeric_smiles 含手性标记 @，
    21376 行的两列不同。只读 smiles 会把立体化学整个丢掉——
    而中药成分（糖苷、萜类、生物碱）正是手性重灾区。
    """
    import sqlite3
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name_en, smiles, isomeric_smiles FROM compounds "
            "WHERE smiles IS NOT NULL AND smiles != '' AND LENGTH(smiles) > 3 LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    out = []
    for name, smiles, iso in rows:
        use = (iso or "").strip()
        if not use or use in ("Not", "not", "None", "none", "N/A", "NA"):
            use = (smiles or "").strip()
        if not use:
            continue
        m = Chem.MolFromSmiles(use)
        if m is not None:
            out.append((name or "", use, m))
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="chemreact 规则校验器")
    ap.add_argument("--rules", default=str(here / "rules.json"))
    ap.add_argument("--db", default=r"D:\TCMAI\tcm.db")
    ap.add_argument("--limit", type=int, default=4000, help="取多少个真实底物")
    ap.add_argument("--report", default=None, help="把 Markdown 报告写到这个路径")
    ap.add_argument("--engine", default="rdchiral", choices=["rdkit", "rdchiral"],
                    help="反应引擎。默认 rdchiral —— 实测：rdkit 原生 RunReactants 在"
                         "『反应断开的键位于环内』时会复制环上原子（凭空造原子），"
                         "rdchiral 能正确把环打开成一条链。"
                         "只有在必须用 rdkit 时，才需要给相关 SMARTS 加 !@ 环键约束。")
    ap.add_argument("--strip-ring-constraint", action="store_true",
                    help="加载时去掉 SMARTS 里的 !@ 环键约束（历史上用于对比实验，现已无规则含 !@）")
    ap.add_argument("--sprawl-threshold", type=float, default=3.0,
                    help="平均每个底物产出超过多少个产物就算「泛滥」（默认 3.0）")
    ap.add_argument("--libs", default=str(Path(__file__).resolve().parent.parent / "libs"),
                    help="rdchiral 等外挂包的目录（不污染项目 venv）")
    args = ap.parse_args(argv)

    if args.engine == "rdchiral":
        if Path(args.libs).is_dir():
            sys.path.insert(0, args.libs)
        try:
            import rdchiral  # noqa: F401
        except Exception as e:
            print(f"[错误] 需要 rdchiral 才能用 --engine rdchiral: {e}")
            print(f"       可用以下命令装到独立目录（不动项目 venv）：")
            print(f"       python -m pip install --target \"{args.libs}\" --no-deps rdchiral")
            return 2

    profiles, rules = load_rules(args.rules)

    if args.strip_ring_constraint:
        n = 0
        for r in rules:
            if "!@" in r.get("smarts", ""):
                r["smarts"] = r["smarts"].replace("!@", "")
                n += 1
        print(f"（对比实验：已去掉 {n} 条规则的 !@ 环键约束）")

    print(f"规则文件: {args.rules}")
    print(f"规则条数: {len(rules)}   条件模板: {len(profiles)}   引擎: {args.engine}")

    substrates = _load_substrates(args.db, args.limit)
    print(f"真实底物: {len(substrates)} 个（只读自 {args.db}）\n")

    reports = [validate_rule(r, profiles, substrates, engine=args.engine) for r in rules]

    # 已知坏、已停用的规则照旧列出（提醒有人去修），但不计入退出码，
    # 否则 CI 永远红灯，红灯就失去意义了。
    disabled_ids = {r["id"] for r in rules if r.get("status") == "disabled"}

    order = {"STATIC_FAIL": 0, "DEAD_RULE": 1, "ATOM_CREATION": 2,
             "UNBALANCED": 3, "NO_SUBSTRATE": 4, "PASS_PROBE": 5, "PASS": 6}
    reports.sort(key=lambda x: order.get(x["verdict"], 9))

    print(f"{'规则':<22}{'结论':<16}{'匹配':>5}{'产例':>6}{'配平':>6}"
          f"{'造原子':>7}{'漏片段':>7}{'产物/分子':>10}  泛滥/限流")
    print("-" * 96)
    limits = {r["id"]: r.get("max_products_per_molecule") for r in rules}
    sprawl = []
    for rep in reports:
        bal = rep["balance"] or {}
        flag = " [已停用]" if rep["id"] in disabled_ids else ""
        ppm = bal.get("products_per_molecule", 0.0)
        lim = limits.get(rep["id"])
        # 只有【没设上限】才算问题。设了上限 = 已接受的处理方式，不再报警。
        is_sprawl = ppm > args.sprawl_threshold and lim is None
        if is_sprawl:
            sprawl.append((rep["name"], ppm))
        marker = "★泛滥★" if is_sprawl else (f"限 {lim}" if lim else "")
        print(f"{rep['name'] or rep['id']:<22}{rep['verdict']+flag:<16}"
              f"{bal.get('matched_substrates', '-'):>5}"
              f"{bal.get('product_sets_checked', '-'):>6}"
              f"{bal.get('balanced', '-'):>6}"
              f"{bal.get('atom_creation', '-'):>7}"
              f"{bal.get('atom_loss', '-'):>7}"
              f"{ppm:>10}  {marker}")
        for p in rep["static_problems"]:
            print(f"      · 静态问题: {p}")
        for ex in (bal.get("examples") or []):
            print(f"      · {ex['kind']} | {ex['substrate'][:30]}: "
                  f"右减左 {ex['diff_right_minus_left']}")

    counts: Counter = Counter(r["verdict"] for r in reports)
    print("\n" + "=" * 96)
    for v in ("PASS", "PASS_PROBE", "NO_SUBSTRATE", "UNBALANCED", "ATOM_CREATION",
              "DEAD_RULE", "STATIC_FAIL"):
        if counts[v]:
            print(f"{v:<14}{counts[v]} 条")
    print("=" * 96)

    if sprawl:
        print(f"\n⚠ 产物泛滥（平均每个底物产出 > {args.sprawl_threshold} 个，且未设上限）：")
        for name, ppm in sorted(sprawl, key=lambda x: -x[1]):
            print(f"    {name:<22}{ppm:>8} 个/分子")
        print("  泛滥不等于失衡——这些规则配平可能是对的，但没有区域选择性，")
        print("  等于「给每个位置都加一个羟基」，对预测没有价值。")
        print("  治法：① 用 max_products_per_molecule 限流（原作者的 RULE_LIMITS 已迁移）；")
        print("        ② 或收紧 SMARTS 加取代基/电子效应约束（需要化学判断）。")
    else:
        n_limited = sum(1 for v in limits.values() if v)
        print(f"\n✓ 无未限流的泛滥规则（{n_limited} 条已设产物数上限）")

    if args.report:
        _write_markdown(args.report, reports, counts, len(rules), len(substrates),
                        disabled_ids, limits)
        print(f"\nMarkdown 报告已写入: {args.report}")

    bad = [r for r in reports
           if r["id"] not in disabled_ids
           and r["verdict"] in ("ATOM_CREATION", "UNBALANCED", "DEAD_RULE",
                                "STATIC_FAIL")]
    n_disabled_bad = sum(1 for r in reports
                         if r["id"] in disabled_ids
                         and r["verdict"] in ("ATOM_CREATION", "UNBALANCED",
                                              "DEAD_RULE", "STATIC_FAIL"))
    if n_disabled_bad:
        print(f"（另有 {n_disabled_bad} 条已停用的坏规则，不计入退出码，但别忘去修）")
    return 1 if bad else 0


def _write_markdown(path: str, reports: List[Dict[str, Any]], counts: Counter,
                    n_rules: int, n_substrates: int,
                    disabled_ids: Optional[set] = None,
                    limits: Optional[Dict[str, Any]] = None) -> None:
    disabled_ids = disabled_ids or set()
    limits = limits or {}
    lines: List[str] = []
    lines.append("# 规则库自动校验报告\n")
    engine = reports[0].get("engine", "?") if reports else "?"
    lines.append(f"- 反应引擎：**{engine}**")
    lines.append(f"- 规则总数：**{n_rules}**"
                 f"（其中已停用 {len(disabled_ids)} 条，不计入退出码）")
    lines.append(f"- 真实底物样本：**{n_substrates}** 个")
    lines.append("- 判据：`原子(底物) + 原子(co_reagents) == 原子(SMARTS产物) + 原子(byproducts)`\n")
    lines.append("## 汇总\n")
    lines.append("| 结论 | 条数 | 含义 |")
    lines.append("|---|---|---|")
    meaning = {
        "PASS": "静态 + 配平全过",
        "PASS_PROBE": "样本覆盖不到，但人工指定底物跑通且配平 —— 置信度来自人工验证，不是大规模抽样",
        "NO_SUBSTRATE": "静态通过，样本里没有底物匹配，且未提供人工底物 —— 只说明无法证伪，不等于规则错了",
        "UNBALANCED": "产物原子数 < 底物：漏写了产物片段（如 CO2），补上即可",
        "ATOM_CREATION": "产物原子数 > 底物：SMARTS 模板写坏，RDKit 复制了原子，必须重写规则",
        "DEAD_RULE": "能匹配底物但产不出任何产物",
        "STATIC_FAIL": "SMARTS 编译失败 / 字段缺失 / 条件窗口非法",
    }
    for v in ("PASS", "PASS_PROBE", "NO_SUBSTRATE", "UNBALANCED", "ATOM_CREATION",
              "DEAD_RULE", "STATIC_FAIL"):
        if counts[v]:
            lines.append(f"| `{v}` | {counts[v]} | {meaning[v]} |")

    lines.append("\n## 逐条明细\n")
    lines.append("| 规则 | 结论 | 匹配底物 | 产生例 | 配平 | 凭空造原子 | 漏写片段 | 产物/分子 | 上限 | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for rep in reports:
        bal = rep["balance"] or {}
        note = "; ".join(rep["static_problems"])
        for ex in (bal.get("examples") or [])[:1]:
            note += f"{ex['kind']} {ex['substrate'][:24]}: 右减左 {ex['diff_right_minus_left']}"
        label = rep["name"] or rep["id"]
        if rep["id"] in disabled_ids:
            label += " ⏸"
            note = "【已停用，不计入退出码】" + note
        ppm = bal.get("products_per_molecule", 0.0)
        lim = limits.get(rep["id"])
        if lim is None and ppm > 3.0:
            note = "★泛滥且未限流★ " + note
        lines.append(
            f"| {label} | `{rep['verdict']}` | "
            f"{bal.get('matched_substrates', '-')} | {bal.get('product_sets_checked', '-')} | "
            f"{bal.get('balanced', '-')} | {bal.get('atom_creation', '-')} | "
            f"{bal.get('atom_loss', '-')} | {ppm} | {lim if lim else '—'} | {note} |"
        )

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
