# -*- coding: utf-8 -*-
"""
chemreact 核心：反应引擎（单步）
================================

职责：给定「一条规则 + 一个底物 + 一组条件」，产出候选产物，并带上完整来源追溯。

★ 本模块正面修掉了原 tcm_analyzer.py 的一个硬伤 ★

原代码：
    def _valid_product(mol, min_mw=100, min_heavy=10):
        ...
        if Descriptors.MolWt(mol) < min_mw: return False
        if mol.GetNumHeavyAtoms() < min_heavy: return False

后果（第 0 轮实测）：**苯甲酸（MW 122，9 个重原子）被过滤掉**。
而乌头碱"酯水解减毒"的标志性产物正是苯甲酸 + 乙酸——两个都被当成"噪声"删了。
演示给中药学院的老师看，这一条一问就露馅。

本模块的做法不是"把阈值调小"，而是**不删数据、只做分类**：

    · 价态非法          → 丢弃（这是真正的坏数据）
    · 单原子 / 分子量 < 2 → 丢弃（H+、单个离子之类，不是产物）
    · 小分子副产物       → **保留**，但打上 is_byproduct 标记
                          （水 18、甲醇 32、CO2 44 这类）
    · 其余              → 正常产物

这样上层 UI 可以默认折叠副产物，但化学账目始终是完整的、可追溯的。
「删掉不该删的」比「显示太多」危险得多——前者会静默改变结论。
"""

from __future__ import annotations

import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

RDLogger.DisableLog("rdApp.error")
RDLogger.DisableLog("rdApp.warning")

_HERE = Path(__file__).resolve().parent
_STAGE = _HERE.parent
for _p in (_STAGE / "rules", _STAGE / "conditions", _STAGE / "libs"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from schema import load_rules, resolve_conditions          # noqa: E402
from model import Conditions                                # noqa: E402
from activator import active_rules, activation_score        # noqa: E402


# ---------------------------------------------------------------- 阈值

# 低于这个分子量、或重原子数不超过这个值的，标记为「小分子副产物」。
# 注意：是【标记】不是【删除】。
BYPRODUCT_MAX_MW = 46.0        # 水 18、甲醇 32、CO2 44 都落在这里；甲酸 46 恰好在上界
BYPRODUCT_MAX_HEAVY = 2

# 真正的丢弃门槛：低于此值说明根本不是个分子（H+、单原子离子）
DISCARD_MIN_MW = 2.0


# ---------------------------------------------------------------- 数据结构

@dataclass
class Compound:
    """一个输入成分（来自药材，或来自上一轮级联）。"""
    smiles: str
    name: str = ""
    herb: str = ""
    source: str = ""            # "herb" | "cascade" | "user"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Product:
    """一个候选产物，自带完整来源追溯（项目简报 §10）。"""
    smiles: str
    formula: str
    mw: float
    heavy_atoms: int

    rule_id: str
    rule_name: str
    category: str

    source_smiles: str
    source_name: str
    source_herb: str

    round: int = 0
    score: float = 0.0
    is_byproduct: bool = False
    reversible: bool = False
    activation: float = 0.0

    # ★ 第三十四轮：activation 的**依据**（"温度窗口命中"/"溶剂不匹配降权"/"试剂角色不匹配"…）。
    #   动机（实测）：条件层常给出 0.5 这种值，但它其实是"我没匹配上"，
    #   用户看到 0.5 会误当成"模型判断有一半把握"。把依据带出来，误读就消失了。
    activation_why: str = ""

    # ★ 与它同时产生的其他片段（含自己）。
    # 有了这个才能算反应 ΔG——单独一个产物构不成配平的方程。
    co_products: tuple = ()
    # ★ D1（2026-10-13）：(dC, dH, dO) = 产物 - 反应物；方向层的「元素收支形状」判据用。空元组 = 没算。
    element_delta: tuple = ()
    # ★ D2（2026-10-13）：同一反应里**另一个**底物的规范化 SMILES（条件模型要两个指纹位）。
    partner_smiles: str = ""
    # ★ D5（2026-10-13）：这条产物来自的 3 组分模板 support（0 = 不适用/非三组分）。
    #   用途只有一个：给「只见过一次的套路」打标记（不删产物、不排序）。
    template_support: int = 0

    # ★ 热力学（由 core/thermo.py 填充，可为空）
    dg_kj: Optional[float] = None
    stability: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def describe(self) -> str:
        tag = " [副产物]" if self.is_byproduct else ""
        return (f"{self.formula:<12} {self.rule_name:<12} "
                f"来自 {self.source_name or self.source_smiles[:16]:<18} "
                f"第{self.round}轮 置信 {self.score:.3f}{tag}")


# ---------------------------------------------------------------- 分子缓存

_MOL_CACHE: Dict[str, Optional[Chem.Mol]] = {}


def get_mol(smiles: str) -> Optional[Chem.Mol]:
    if smiles not in _MOL_CACHE:
        m = Chem.MolFromSmiles(smiles)
        if m is not None:
            try:
                Chem.SanitizeMol(m)
            except Exception:
                m = None
        _MOL_CACHE[smiles] = m
    return _MOL_CACHE[smiles]


def classify_product(mol: Chem.Mol) -> Tuple[bool, bool]:
    """返回 (是否保留, 是否小分子副产物)。

    这是对原 _valid_product 的替代。**只丢真正不是分子的东西**，
    小分子一律保留但打标记。
    """
    try:
        if Chem.SanitizeMol(Chem.Mol(mol), catchErrors=True) != Chem.SanitizeFlags.SANITIZE_NONE:
            return False, False
    except Exception:
        return False, False

    mw = Descriptors.MolWt(mol)
    heavy = mol.GetNumHeavyAtoms()

    if mw < DISCARD_MIN_MW or heavy < 1:
        return False, False          # H+、单原子离子

    is_byproduct = (mw <= BYPRODUCT_MAX_MW) or (heavy <= BYPRODUCT_MAX_HEAVY)
    return True, is_byproduct


# ---------------------------------------------------------------- 原子计数
# 运行时原子守恒守卫用的小工具。
# 不 import rules/schema.py 的实现，是为了不让 core 依赖 rules 层。

_FORMULA_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)")

# 原子计数缓存。守恒守卫对每个产物组都要算一次，
# cProfile 显示这块占了约 10% 的时间；同一个 SMILES 会被反复算。
_ATOM_COUNT_CACHE: Dict[str, Dict[str, float]] = {}


def _formula_atoms(formula: str) -> Dict[str, float]:
    """把 'C6H6O2' 解析成 {'C':6,'H':6,'O':2}。支持小数（如 O2 的 0.5 倍）。"""
    out: Dict[str, float] = {}
    for el, cnt in _FORMULA_TOKEN.findall(formula or ""):
        if not el:
            continue
        out[el] = out.get(el, 0.0) + (float(cnt) if cnt else 1.0)
    return out


def _atom_counts_of_smiles(smiles: str) -> Dict[str, float]:
    """含氢的完整原子计数。解析失败返回空字典（调用方据此保守放行）。

    ★ 带缓存 ★ 守恒守卫对每个产物片段都要调用一次，而同一个 SMILES
    会在不同产物组里反复出现（例如水、葡萄糖）。

    ★★ 必须返回【副本】★★
      踩过的坑：第一版直接返回缓存里那个 dict，而 _collect 里会原地加
      co_reagents（`left[el] = left.get(el,0)+c*v`），于是把缓存改脏了 ——
      同一个底物的原子数被越加越多，守卫判定"配不平"，产物从 455 个掉到 18 个。
      缓存可以共享，但共享出去的对象【绝不能被调用方改】。
    """
    key = smiles
    hit = _ATOM_COUNT_CACHE.get(key)
    if hit is not None:
        return dict(hit)
    m = get_mol(smiles)
    if m is None:
        _ATOM_COUNT_CACHE[key] = {}
        return {}
    mh = Chem.AddHs(m)
    out: Dict[str, float] = {}
    for a in mh.GetAtoms():
        s = a.GetSymbol()
        out[s] = out.get(s, 0.0) + 1.0
    _ATOM_COUNT_CACHE[key] = out
    return dict(out)


def _add_counts(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0.0) + v
    return out


def _counts_differ(a: Dict[str, float], b: Dict[str, float],
                   tol: float = 1e-6) -> bool:
    """两边原子数是否不同。任一边为空（解析失败）时返回 False（保守放行）。"""
    if not a or not b:
        return False
    for k in set(a) | set(b):
        if abs(a.get(k, 0.0) - b.get(k, 0.0)) > tol:
            return True
    return False


# ---------------------------------------------------------------- 引擎

class Engine:
    """单步反应引擎。规则编译结果会缓存，可反复用。"""

    def __init__(self, rules: Sequence[Dict[str, Any]],
                 profiles: Dict[str, Any],
                 default_max_products: int = 3):
        self.rules = list(rules)
        self.profiles = dict(profiles)
        self.default_max_products = default_max_products
        self._rxn_cache: Dict[str, Any] = {}
        self._nreact_cache: Dict[str, int] = {}
        self._rdkit_rxn_cache: Dict[str, Any] = {}
        self._missing_rdchiral_reported = False
        # ★ 性能：按 SMILES 缓存 rdchiralReactants（原来每条规则都重建一次）
        self._reactants_cache: Dict[str, Any] = {}
        # ★ 性能：按规则 id 缓存反应物模板，供便宜预筛用
        self._template_cache: Dict[str, Any] = {}

    # -------------------------------------------------- rdchiral 编译缓存

    def _reaction(self, rule: Dict[str, Any]):
        rid = rule["id"]
        if rid not in self._rxn_cache:
            from rdchiral.main import rdchiralReaction
            self._rxn_cache[rid] = rdchiralReaction(rule["smarts"])
        return self._rxn_cache[rid]

    # -------------------------------------------------- 反应物模板数

    def n_reactants(self, rule: Dict[str, Any]) -> int:
        """这条规则有几个反应物模板。

        rdchiral 的 rdchiralRun 里写死了 RunReactants((mol,))——单元素元组，
        所以双反应物规则必须走 rdkit 原生引擎。
        这类规则（酯交换、席夫碱、酯化…）断的通常是非环键，
        配合 !@ 约束可行；环状的情况交给对应的单反应物规则。
        """
        rid = rule["id"]
        if rid not in self._nreact_cache:
            try:
                rxn = AllChem.ReactionFromSmarts(rule["smarts"])
                self._nreact_cache[rid] = rxn.GetNumReactantTemplates() if rxn else 0
            except Exception:
                self._nreact_cache[rid] = 0
        return self._nreact_cache[rid]

    def _rdkit_reaction(self, rule: Dict[str, Any]):
        rid = rule["id"]
        if rid not in self._rdkit_rxn_cache:
            self._rdkit_rxn_cache[rid] = AllChem.ReactionFromSmarts(rule["smarts"])
        return self._rdkit_rxn_cache[rid]

    # -------------------------------------------------- 第二反应物池

    def available_cosubstrates(self, rule: Dict[str, Any],
                               cond: Optional[Conditions] = None):
        """按当前条件筛出这条规则可用的第二反应物。

        ★ 池子受条件约束：醇提时才有乙醇，煎煮时只有水。
          这正是「醇提 ≠ 水提」在化学上落地的关键——
          乙醇不只改变速率，它本身就参与反应（酯交换）。
        """
        out = []
        for item in (rule.get("co_substrate_pool") or []):
            if not isinstance(item, dict) or not item.get("smiles"):
                continue
            when = item.get("when_solvent")
            if when and cond is not None and cond.solvent not in when:
                continue
            out.append(item)
        return out

    # -------------------------------------------------- 单条规则 × 单个底物

    def apply_rule(self, rule: Dict[str, Any], sub: Compound,
                   activation: float, round_no: int,
                   cond: Optional[Conditions] = None) -> List[Product]:
        n = self.n_reactants(rule)
        if n == 2:
            return self._apply_bireactant(rule, sub, activation, round_no, cond)
        return self._apply_rdchiral(rule, sub, activation, round_no)

    # -------------------------------------------------- 单反应物（rdchiral）

    def _reactants_obj(self, smiles: str):
        """按 SMILES 缓存 rdchiralReactants —— 同一个底物只构造一次。

        ★ 为什么必须缓存 ★
          rdchiralReactants(smiles) 的初始化很贵（要指派立体化学、
          给每个原子分配 map number）。原来在 _apply_rdchiral 里
          【每条规则都重新构造一次同一个对象】：
              43 条规则 × 59 个底物 = 2537 次
          cProfile 显示 initialization.py 占 36% 的时间，就是这么来的。
          缓存后降到 59 次。
        """
        key = smiles
        if key not in self._reactants_cache:
            from rdchiral.main import rdchiralReactants
            self._reactants_cache[key] = rdchiralReactants(smiles)
        return self._reactants_cache[key]

    def _achiral_matches(self, rule: Dict[str, Any], reactants_obj) -> bool:
        """便宜预筛：底物（非手性版）到底匹不匹配这条规则的模板？

        ★ 为什么安全 ★
          rdchiral/main.py:121 的第一步是
              outcomes = rxn.rxn.RunReactants((reactants.reactants_achiral,))
              if not outcomes: return []
          RunReactants 是【基于子结构匹配】的：匹配不上必然返回空。
          所以「模板匹配失败 ⇒ 结果必为空」是确定的，
          预筛只会跳过注定为空的调用，不会丢掉任何产物。

        ★ 必须用【非手性】分子 ★
          rdchiral 匹配的是 reactants_achiral。若拿带手性的底物去匹配
          带 @ 的模板，会误判为不匹配（实测 2-丁醇的 R/S 异构体都会挂）。
          用错会静默丢产物 —— 这是这个优化唯一的坑。
        """
        tid = rule["id"]
        patt = self._template_cache.get(tid)
        if patt is None:
            rxn = self._rdkit_reaction(rule)
            if rxn is None:
                self._template_cache[tid] = False
                return True          # 编译不了就放行，交给 rdchiral 自己失败
            patt = rxn.GetReactantTemplate(0)
            self._template_cache[tid] = patt
        if patt is False:
            return True
        try:
            return reactants_obj.reactants_achiral.HasSubstructMatch(patt)
        except Exception:
            return True              # 出意外就放行（宁可慢，不可错）

    def _apply_rdchiral(self, rule: Dict[str, Any], sub: Compound,
                        activation: float, round_no: int) -> List[Product]:
        from rdchiral.main import rdchiralRun

        try:
            rxn = self._reaction(rule)
            r_obj = self._reactants_obj(sub.smiles)
            # ---- 便宜预筛：77.5% 的 (规则×底物) 组合在这一步就跳过了 ----
            if not self._achiral_matches(rule, r_obj):
                self.prefilter_skipped = getattr(self, "prefilter_skipped", 0) + 1
                return []
            outcomes = rdchiralRun(rxn, r_obj) or []
        except Exception:
            return []
        return self._collect(rule, sub, activation, round_no, outcomes,
                             co_substrate=None)

    # -------------------------------------------------- 双反应物（rdkit 原生）

    def _apply_bireactant(self, rule: Dict[str, Any], sub: Compound,
                          activation: float, round_no: int,
                          cond: Optional[Conditions]) -> List[Product]:
        candidates = self.available_cosubstrates(rule, cond)
        if not candidates:
            return []

        sub_mol = get_mol(sub.smiles)
        if sub_mol is None:
            return []
        rxn = self._rdkit_reaction(rule)
        if rxn is None:
            return []

        limit = rule.get("max_products_per_molecule", self.default_max_products)
        out: List[Product] = []
        seen_local = set()

        for item in candidates:
            co_mol = get_mol(item["smiles"])
            if co_mol is None:
                continue
            try:
                res = rxn.RunReactants((sub_mol, co_mol))
            except Exception:
                continue
            outcomes = []
            for pset in res:
                frags = []
                for p in pset:
                    pc = Chem.Mol(p)
                    try:
                        Chem.SanitizeMol(pc)
                    except Exception:
                        frags = None
                        break
                    frags.append(Chem.MolToSmiles(pc))
                if frags:
                    outcomes.append(".".join(frags))
            if not outcomes:
                continue
            out = self._collect(rule, sub, activation, round_no, outcomes,
                                co_substrate=item, limit=limit,
                                seen_local=seen_local)
            if out:
                break       # 池子里第一个能反应的分子就够了
        return out

    # -------------------------------------------------- 产物整理

    def _collect(self, rule: Dict[str, Any], sub: Compound,
                 activation: float, round_no: int,
                 outcomes: Sequence[str],
                 co_substrate: Optional[Dict[str, Any]] = None,
                 limit: Optional[int] = None,
                 seen_local: Optional[set] = None) -> List[Product]:
        if limit is None:
            limit = rule.get("max_products_per_molecule", self.default_max_products)
        if seen_local is None:
            seen_local = set()

        # ★★ 必须排序：跨进程可复现的前提 ★★
        #
        # 实测事故：同一个脚本在独立进程里跑 5 次，
        #   产物数 462 / 461 / 463 / 458 / 458
        # 固定 PYTHONHASHSEED=0 之后：
        #   452 / 452 / 452 —— 完全一致
        #
        # 根因在 rdchiral：libs/rdchiral/main.py:131
        #     final_outcomes = set()
        #     ...
        #     return [list(x) for x in final_outcomes]
        # 它用【集合】收集结果，转 list 时顺序随 Python 的字符串哈希种子变化。
        # 而下面有 `if len(out) >= limit: break` —— 取"前 N 个"，
        # 于是每个进程截断下来的产物不一样。
        #
        # 排序后，同一组产物在哪个进程都排在同一个位置，截断结果就确定了。
        outcomes = sorted(outcomes)

        # ★★ 运行时原子守恒守卫 ★★
        #
        # 为什么需要它（实测动机）：
        #   「对醌还原」这条规则的 SMARTS 用 ~（任意键）匹配
        #   [O]=[C]~[C]~[C]~[C]=[O]。出乎意料的是，它会顺带匹配上
        #   甾体 3,6-二酮这种【两个 C=O 分处不同环】的结构——
        #   因为那两个碳之间除了直路，还有一条绕环的远路。
        #   而这类结构的产物【无法芳香化】，RDKit 不给碳补氢，
        #   于是产物比底物少 2 个氢 —— 配不平。
        #
        #   试过 6 种 SMARTS 约束都排不掉（环内键 @、环成员 R、
        #   递归 SMARTS、六元环 r6、反应物侧环闭合……）。
        #
        # 所以换一个层面解决：**在引擎里守一道**。
        #   规则声明了 co_reagents / byproducts，那么
        #       底物 + 陪跑试剂 − 副产物  ==  产物
        #   必须成立。不成立说明这个产物是错的，直接丢掉。
        #
        # 这是通用防线：不止管这一条规则，任何规则（现在或将来）
        # 产出配不平的产物都会被当场拦下。
        #
        # ★ 多片段底物（盐、离子对）要放行 ★
        #   实测：10-十一烯酸钠 C=CCCCCCCCCC(=O)[O-].[Na+] 会被误杀——
        #   rdchiral 只返回参与反应的那一片，Na+ 留在原地，
        #   于是「产物原子数」天然对不上底物。
        #   这类底物（含 . 的 SMILES）整个跳过守卫。
        _sub_mol = get_mol(sub.smiles)
        _guard_on = (_sub_mol is not None
                     and len(Chem.GetMolFrags(_sub_mol)) == 1)

        # ★ 注意：守卫关闭时，left 必须【保持为空】★
        #   第一版写成 left = {} 然后照样把 co_reagents 加进去，
        #   结果这个底物有 co={H2:1}，left 变成了 {H:2}（非空），
        #   _counts_differ 的「任一边为空就放行」短路失效，照样误杀。
        left: Dict[str, float] = {}
        declared: Dict[str, float] = {}
        if _guard_on:
            left = _atom_counts_of_smiles(sub.smiles)
            if co_substrate and co_substrate.get("smiles"):
                left = _add_counts(left,
                                   _atom_counts_of_smiles(co_substrate["smiles"]))
            for formula, n in (rule.get("co_reagents") or {}).items():
                v = float(n)
                for el, c in _formula_atoms(formula).items():
                    left[el] = left.get(el, 0.0) + c * v
            for formula, n in (rule.get("byproducts") or {}).items():
                v = float(n)
                for el, c in _formula_atoms(formula).items():
                    declared[el] = declared.get(el, 0.0) + c * v

        out: List[Product] = []
        n_unbalanced = 0
        for smi in outcomes:
            if len(out) >= limit:
                break

            # ---- 守卫：这一组产物的原子数必须配得平 ----
            right = dict(declared)
            for part in (p for p in smi.split(".") if p):
                for el, c in _atom_counts_of_smiles(part).items():
                    right[el] = right.get(el, 0.0) + c
            if _counts_differ(left, right):
                n_unbalanced += 1
                continue

            # 先把这一组产物全部过一遍有效性检查，
            # 因为算反应 ΔG 需要知道「这个产物是和哪些同伴一起产生的」，
            # 单独一个片段构不成配平的方程。
            parts = [p for p in smi.split(".") if p]
            valid = []
            for part in parts:
                if part in seen_local:
                    continue
                mol = get_mol(part)
                if mol is None:
                    continue
                keep, is_by = classify_product(mol)
                if not keep:
                    continue
                valid.append((part, mol, is_by))

            if not valid:
                continue
            group = tuple(sorted(p for p, _m, _b in valid))

            for part, mol, is_by in valid:
                seen_local.add(part)
                out.append(Product(
                    smiles=part,
                    formula=rdMolDescriptors.CalcMolFormula(mol),
                    mw=round(Descriptors.MolWt(mol), 2),
                    heavy_atoms=mol.GetNumHeavyAtoms(),
                    rule_id=rule["id"],
                    rule_name=rule["name"],
                    category=rule.get("category", ""),
                    source_smiles=sub.smiles,
                    source_name=sub.name,
                    source_herb=sub.herb,
                    round=round_no,
                    is_byproduct=is_by,
                    reversible=bool(rule.get("reversible", False)),
                    activation=activation,
                    co_products=group,
                ))
        if n_unbalanced:
            self.balance_dropped = getattr(self, "balance_dropped", 0) + n_unbalanced
        return out

    # -------------------------------------------------- 一步：底物池 × 激活规则

    def step(self, compounds: Sequence[Compound], cond: Conditions,
             threshold: float = 0.15,
             exclude_smiles: Optional[set] = None,
             round_no: int = 1) -> List[Product]:
        """对一批底物跑一轮反应。exclude_smiles 里的产物不再重复产出。"""
        exclude_smiles = exclude_smiles or set()
        active = active_rules(self.rules, self.profiles, cond, threshold)

        results: List[Product] = []
        seen: set = set()

        for sub in sorted(compounds, key=lambda c: c.smiles):
            # ★ 必须排序 ★
            #   同一个产物 SMILES 可能由多个底物产出，而这里「谁先产出谁记名」
            #   （`if p.smiles in seen: continue`）。
            #   不排序的话，产物的 source_smiles / source_name 就取决于
            #   调用方传底物的顺序 —— 实测 153 个产物里有 23 个（15%）归属会变，
            #   而 source_smiles 又参与打分（一致性因子），
            #   于是级联的前沿选择跟着变，整条链路的输出都不可复现。
            if get_mol(sub.smiles) is None:
                continue
            for rule, act, _reasons in active:
                for p in self.apply_rule(rule, sub, act, round_no=round_no,
                                         cond=cond):
                    if p.smiles in exclude_smiles or p.smiles in seen:
                        continue
                    if p.smiles == sub.smiles:
                        continue          # 自身不算产物
                    seen.add(p.smiles)
                    results.append(p)
        return results


# ---------------------------------------------------------------- 便捷入口

def load_engine(rules_path: Optional[str] = None) -> Tuple[Engine, List[Dict], Dict]:
    p = Path(rules_path) if rules_path else (_STAGE / "rules" / "rules.json")
    profiles, rules = load_rules(p)
    return Engine(rules, profiles), rules, profiles
