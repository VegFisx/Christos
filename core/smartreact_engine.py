# -*- coding: utf-8 -*-
r"""★ SmartReact 后端的 Engine —— 把新规则库接进旧引擎架构 ★

## 为什么要这个

上个会话建了一整套引擎架构（`core/engine.py`、`cascade.py`、`scorer.py`、`thermo.py`），
但它是建在**已作废的 63 条论文规则**上的。而 cascade/scorer/thermo/检查体系都是好资产。

`core/cascade.py` 对引擎的要求其实很薄：
  · `engine.rules`              —— 至少每项有 "id"
  · `engine.step(compounds, cond, threshold, exclude_smiles, round_no) -> List[Product]`

本模块提供这两个，于是 **级联（多步 + 三组分）/ 排序 / 热力学 / 检查体系全部立刻可用**，
规则库换成 SmartReact 的 9770 条模板。

## 粒度说明（重要）

旧引擎的"规则"是一条条命名的规则；SmartReact 的 9770 条模板实际归属 37 种**反应类型**。
`ReactionResult` 只给出 `reaction_name`，不给 template_id，
所以这里**以【反应类型】为规则粒度**（37 条），而不是 9770 条。
这样 `rule_id = reaction_name`，与 cascade 的 `rule_by_id` 天然对齐。

## 防组合爆炸

两个闸门：
  · `max_products_per_pair` —— 单个底物对最多产出多少个产物
    （实测教训：甘草 15 对曾产出 59,653 个产物，其中 1 对出了 35,521 个酯）
  · `max_pairs` —— 单轮最多跑多少对（frontier 很大时截断）

用法（自检）: python smartreact_engine.py
"""
from __future__ import annotations

import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_STAGE = Path(__file__).resolve().parent.parent
for _p in (_STAGE / "core", _STAGE / "conditions", _STAGE / "rules", _STAGE / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdMolDescriptors  # noqa: E402  （D1 元素收支用）

from engine import Compound, Product, classify_product, get_mol  # noqa: E402

# ★ 溶剂词表（第十二轮）：单一真相在 conditions/model.py，不在这里重复维护 ★
from model import solvent_class, solvent_matches  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TEMPLATES = _STAGE / "libs" / "smartreact" / "data" / "templates.txt"
CONDITION_TABLE = _STAGE / "reports" / "conditions_by_reaction_type.json"
# ★ 第十二轮：必需试剂判据用的覆盖率表（tools/run_aux_reagent_coverage.py 产出）★
COVERAGE_TABLE = _STAGE / "reports" / "aux_reagent_coverage.json"
# ★ 第十六轮（2026-10-13）：ORD 自抽正向模板的默认位置 —— 默认【开】（K1 档）★
# ★ 第六十六轮（2026-10-15）：切到【全量挖矿】库（s5 文件）。
# ★ 第六十八轮（2026-10-15，用户 proceed）：砍掉速度妥协，直接上论文最优档——
#   extra 支持>=10、limit 20000；mono limit 6000；max_products_per_pair 8→32；
#   prefilter 默认开（元素门+角色分派，召回逐位一致的实测验收见第六十七轮）。
#   500 样本 75.8%、全量 50k 头条 82.56%（旧 55.43%）。回退旧档：显式传
#   extra_templates_path=旧文件 + 相应 limits + max_products_per_pair=8 + prefilter=False。
DEFAULT_EXTRA_TEMPLATES = _STAGE / "reports" / "mined_forward_templates_full_s5.jsonl"
# ★ 第二十二/二十三/五轮：ORD 自抽【单底物】模板（水解/氧化/还原/消除…）★
#   ORD 里 21.9% 是单底物反应，原来被 forward_template_mining.py 的 `len(plains)!=2` 整类跳过；
#   已用 tools/mine_mono_templates.py 单独挖出（40k 抽样 -> 3,256 条，其中 arity=1 共 2,793、
#   "自给自足"可直接套用 697、需共试剂 1,890 —— 后者留给条件层门控）。
DEFAULT_MONO_TEMPLATES = _STAGE / "reports" / "mined_forward_templates_full_s5.jsonl"
# ★ D5（2026-10-13）：3 组分正向模板（tools/mine_3c_templates.py 产出）
DEFAULT_TRIPLE_TEMPLATES = _STAGE / "reports" / "mined_forward_templates_3c.jsonl"

# ★ B 试点（2026-10-17）：把 6 条 curated 规则以带 reaction_name 的模板接入实时引擎。
#   只在显式 use_curated_templates=True 时加载；默认不改变既有评测。
CURATED_RULE_IDS = {
    "hydrolysis_hemiacetal_001",
    "oxidation_phenol_quinone_001",
    "hydration_enone_001",
    "condensation_hemiacetal_001",
    "addition_thiohemiacetal_001",
    "decarboxylation_cinnamic_001",
}
MINED_TOP_CONDITIONS = _STAGE / "data" / "mined_top_template_conditions.json"

# ★ 第二十四轮：单底物模板的「隐含氧化还原环境」门控（【建模选择】，不是 ORD 实测值）★
#   实测动因：单底物模板接进来后活性 98.2%，但出现"芳环被加氢成环己二烯"这类假产物
#   （Birch 还原需 Na/NH₃，而条件是水/空气）——根因是 needs_co_reagent 只看**重**原子，抓不到改氢数的模板。
#   判据：模板净氢变化 ΔH>0（加氢）→ 需还原环境；ΔH<0（脱氢/氧化）→ 需氧化环境；ΔH=0 → 始终可用。
#   环境从哪来：`Conditions.atmosphere`（model.py 的注释本来就写着"决定氧化/还原反应能不能发生"）
#   + 条件里的试剂 SMILES（简单的关键词表，可扩展）。
# ★★ 但 2026-10-12 实测：**这个门控默认关**（mono_redox_gate=False）★★
#   在 1,500 条真实单底物记录上：门控关 -> 命中 13.2%/活性 98.3%；门控开 -> 命中 **4.1%**/活性 74.1%。
#   即 **砍掉 69% 的命中、只压掉 25% 的活性 = 净亏**。原因：我们 ORD 表的**试剂可得率 0%**，
#   记录里真正用的 NaBH₄ 等还原剂根本不在条件里 -> 门控把**正确的还原**当"气氛不允许"杀掉了。
#   -> 【推断】正确做法是：①先把试剂信息补进条件；②或者**把"抑制"改成"降权"**（不删产物，只压排序）；
#      ③在条件可靠时（如中药煎煮会明确写气氛/试剂）再显式打开本门控。
# ★★ 2026-10-12 续（本轮）：**试剂信息其实一直在**——ORD 的"非贡献组分"就是试剂。
#   实测：单底物记录里 **81.6% 有非贡献组分**，Top 是 `[Na+]`/`[OH-]`/`[H-]`/`[BH4-]`(766)/`[H][H]`(521)/`[Al+3]`/TFA/AcOH/Et3N…
#   把它们填进 `Conditions.reagents` 之后，本门控才可能真正起作用（见 measure_mono_recall_reagents.py）。
#   ★★ 但复测结论仍是**净亏**，所以默认保持 False ★★（1,500 条真实单底物记录）：
#      A 模板关            命中 0.0%   活性 0.0%
#      B 模板开+门控关      命中 13.2%  活性 98.3%   ← 当前默认
#      C 门控开+无试剂      命中 4.1%   活性 74.1%
#      D 门控开+带试剂      命中 6.4%   活性 79.0%
#      E 门控开+带试剂+"无试剂信息不门控"  命中 7.3%  活性 83.3%
#   天花板在哪：**REDUCTANT_HINTS 对真实记录的识别率只有 16.9%**（80.8% 的记录确实带试剂）。
#   -> 【推断】要救这个门控，先得把"试剂角色识别"做成能力（可从业余统计/共现里学），
#      而不是继续调气氛判据。在那之前，本门控保持默认关。
REDUCTANT_HINTS = ("[BH4-]", "[BH3-]", "[BH]", "[AlH", "[Al+3]", "[H-]", "[H][H]", "[SiH]")
OXIDANT_HINTS = ("O=O", "OO", "[Mn", "[Cr", "[I](", "Cl(=O)", "OS(=O)(=O)O", "[O-][O-]")
REDUCING_ATMOS = {"h2"}
OXIDIZING_ATMOS = {"air", "o2"}

# ★ 第十九轮：脱水缩合类反应 —— 在【水相】里视为可逆（不驱动级联传播）★
#   背景（实测）：水相煎煮跑出 8,834 个酯化产物；级联每轮分子量翻倍
#     （底物重原子 51 → 产物 102 → 198 → 407 → 813，第 4 轮已是 MW≈1 万的二聚体），
#     每步耗时 ×6~7（0.58 → 2.01 → 11.5 → 81.3 s），且四轮里被分数门槛拦下 = 0。
#   根因：`Product.reversible` 原来被写死 False —— 旧引擎的可逆性来自 63 条手写规则，
#     换 SmartReact 后没有对应字段，于是 cascade 里 `if p.reversible ...: continue`
#     这道闸门形同虚设，缩合/二聚产物一路传播。
#   ★ 本表是【建模选择】不是 ORD 实测值：脱水缩合（酯化/酰胺/脲/咪唑缩合…）在水相里是平衡反应，
#     按 Le Chatelier 不该往缩合方向被驱动；但在醇相等介质里仍可能被驱动
#     （ROUND7 实测"酯交换 = 醇提的化学实质"），所以本判据【只在介质为水时】生效。
CONDENSATION_CLASSES = frozenset({
    "esterification", "ester_schotten_baumann", "ester_sulfonic_schotten_baumann",
    "amide_coupling", "amine_acetylation", "amine_sulfonation", "urea_formation",
    "imidazole_condensation_acid", "imidazole_condensation_amine",
    "oxadiazole_condensation",
})

# 必需件阈值：覆盖率 >= 0.5 才算"这类反应没有它就做不成"
REQUIRED_COV = 0.5
# 该类反应样本太少（< 20 条）时不敢据此判零
REQUIRED_MIN_N = 20

# ★ 同功能试剂归并（角色）★
#   为什么要归并：DEAD 与 DIAD 都是偶氮二羧酸酯，各自覆盖率可能都 < 0.5，
#   分开看都不"必需"，加起来才是 Mitsunobu 的必需件。
#   ⚠ 这是【建模选择/化学判断】，不是 ORD 实测值；它只用来把实测覆盖率相加。
REAGENT_ROLE_SMARTS = (
    ("phosphine", "[PX3]([#6])([#6])[#6]"),
    ("azodicarboxylate", "[NX2]=[NX2][CX3](=[OX1])[OX2]"),
    ("carbodiimide", "[NX2]=[CX2]=[NX2]"),
    ("uronium_activator", "[NX3+]=[CX3]([NX3])[OX2]"),
    ("benzotriazole", "c1ccc2nnnc2c1"),
    # 还原剂：NaBH4 / NaBH3CN / NaBH(OAc)3 是互相替代的，各自覆盖率可能都不到 0.5
    ("borohydride", "[BH1,BH2,BH3,BH4]"),
    # 有机碱：Et3N / DIPEA / Bu3N 互相替代（不匹配吡啶类：其 N 只有 2 个连接）
    ("trialkylamine", "[NX3]([#6])([#6])[#6]"),
    # 无机碱：碳酸盐 / 磷酸盐 / 氢氧化物 / 醇盐 在同一条反应里是互相替代的。
    # 实测背景（全量 177 万条）：suzuki n=41,470，Na2CO3/K2CO3/Cs2CO3/K3PO4 各自的
    # 碎片覆盖率都 < 0.5（62% 是 [Na+]、56% 是 [K+] 这类反离子），
    # 若不按角色相加，"Suzuki 缺碱"就判不出来。
    ("carbonate_base", "[CX3](=[OX1])([OX1-])[OX1-]"),
    ("phosphate_base", "[PX4](=[OX1])([OX1-])([OX1-])[OX1-]"),
    ("alkoxide_base", "[CX4][OX1-]"),
)


def _load_reaction_names() -> Dict[str, Dict[str, Any]]:
    """从 templates.txt 读每种反应类型的元信息（模板数、底物类别）。"""
    import json
    meta: Dict[str, Dict[str, Any]] = {}
    if not TEMPLATES.exists():
        return meta
    for line in TEMPLATES.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        f = line.split("\t")
        if len(f) != 5:
            continue
        name, tid, _ex, _sm, cats = f
        e = meta.setdefault(name, {"n_templates": 0, "categories": set(), "ids": []})
        e["n_templates"] += 1
        try:
            e["ids"].append(int(tid))
        except ValueError:
            pass
        for c in cats.split("."):
            c = c.strip()
            if c:
                e["categories"].add(c)
    for e in meta.values():
        e["categories"] = sorted(e["categories"])
    return meta


def _load_ord_evidence() -> Dict[str, int]:
    """每种反应类型在 ORD 里被复现过多少次（用于数据驱动的 priority）。"""
    import json
    if not CONDITION_TABLE.exists():
        return {}
    try:
        d = json.loads(CONDITION_TABLE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {k: int(v.get("n_ord_matched", 0)) for k, v in d.items()}


def _formula_counts(formula: str) -> dict:
    """化学式字符串 -> 元素计数（"C84H122O31" -> {"C": 84, "H": 122, "O": 31}）。"""
    out: dict = {}
    for el, num in re.findall(r"([A-Z][a-z]?)(\d*)", formula or ""):
        if not el:
            continue
        out[el] = out.get(el, 0) + (int(num) if num else 1)
    return out


def _element_totals(mols) -> dict:
    """一组分子 -> 元素总计数。★ D1（2026-10-13）：给方向层的「元素收支形状」判据用。

    口径依据（实测）：`libs/smartreact/data/templates.txt` 的 9,770 条模板
    **全部是 2 个反应物模板** —— 所以「两个底物」就是完整的反应物侧，没有额外试剂混在里面，
    元素收支因此良定义。
    """
    tot: dict = {}
    for m in mols:
        if m is None:
            continue
        for el, n in _formula_counts(rdMolDescriptors.CalcMolFormula(m)).items():
            tot[el] = tot.get(el, 0) + n
    return tot


def _element_delta(react_tot: dict, product_formula: str) -> tuple:
    """(dC, dH, dO) = 产物 - 反应物。反应物为空 -> 返回空元组（不判）。"""
    if not react_tot:
        return ()
    pc = _formula_counts(product_formula)
    return (pc.get("C", 0) - react_tot.get("C", 0),
            pc.get("H", 0) - react_tot.get("H", 0),
            pc.get("O", 0) - react_tot.get("O", 0))


# ---------------------------------------------------------------- D5：三组分并行
_TRIPLE_W: dict = {}


def _triple_worker_init(smarts_support):
    """worker 进程初始化：把 (smarts, support) 编译成反应对象（每个 worker 只做一次）。"""
    from rdkit.Chem import rdChemReactions
    comp, fail = [], 0
    for sm, sup in smarts_support:
        try:
            rx = rdChemReactions.ReactionFromSmarts(sm)
        except Exception:
            fail += 1
            continue
        if rx is None:
            fail += 1
            continue
        comp.append((sm, rx, int(sup)))
    _TRIPLE_W["compiled"] = comp
    _TRIPLE_W["fail"] = fail


def _triple_worker(triples):
    """worker：对一批三元组套全部 arity=3 模板 -> [(sa, sb, sc, {产物: support})]。"""
    import rdkit_template_lib as lib
    compiled = _TRIPLE_W.get("compiled") or []
    out = []
    for (sa, sb, sc) in triples:
        try:
            got = lib.apply_triple_support(compiled, get_mol(sa), get_mol(sb), get_mol(sc))
        except Exception:
            continue
        if got:
            out.append((sa, sb, sc, got))
    return out


_AROM2ELEM = {"c": "C", "n": "N", "o": "O", "s": "S", "p": "P", "b": "B"}


def smarts_reactant_elems(sm: str):
    """SMARTS → 两反应物侧的元素需求 (frozenset1, frozenset2)。

    解析不了/三组分以上 → 返回 None（**fail-open**：不下预筛、照常套用）。
    预筛只允许跳过"元素上必然不匹配"的模板——任何召回下降都视为实现 bug（见设计稿口径）。
    """
    try:
        left = str(sm).split(">>")[0]
    except Exception:
        return None
    parts = [p for p in left.split(".") if p]
    if not parts or len(parts) > 2:
        return None
    reqs = []
    for comp in parts:
        elems = set()
        for tok in re.findall(r"\[([^\]]+)\]", comp):
            m = re.match(r"[0-9]*([A-Z][a-z]?)", tok)
            if m:
                elems.add(m.group(1))
                continue
            m2 = re.match(r"[0-9]*([a-z])", tok)
            if m2 and m2.group(1) in _AROM2ELEM:
                elems.add(_AROM2ELEM[m2.group(1)])
                continue
            return None
        rest = re.sub(r"\[[^\]]+\]", " ", comp)
        for t in re.findall(r"Cl|Br|[BCNOFPSIbcnops]", rest):
            elems.add(_AROM2ELEM.get(t, t))
        reqs.append(frozenset(elems))
    return tuple(reqs)


def fair_sample_pairs(n: int, budget: int):
    """公平截断：对子数超预算时，给每个底物**大致同样数量**的伙伴。

    * 与顺序截断（`pairs[:budget]`）的差别（实测口径）：顺序截断下第 1 个成分会与
      其余全部配对，越靠后的成分配到的伙伴越少——n=342 / 预算 4000 时伙伴数约 11~341，
      参与度极不均；公平截断下每个成分伙伴数基本相同（约 2*budget/n，偏差 ≤2）。
    * 确定性：同样 (n, budget) 永远产出同样的对子表（无随机、可复现）。
    * 实现：按"伙伴距离"分层（每层给每个成分 +2 个伙伴），距离在半个环上等步长散开；
      对子总数 ≤ budget，不含重复对。
    """
    if budget <= 0:
        return []
    full = n * (n - 1) // 2
    if budget >= full:
        return [(i, j) for i in range(n) for j in range(i + 1, n)]
    target = max(1, int(round(2.0 * budget / n)))      # 期望伙伴数/成分
    k = max(1, (target + 1) // 2)                      # 层数（每层给每个成分 +2 伙伴）
    step = max(1, (n // 2) // k)                       # 伙伴距离步长（半环内散开）
    out, seen = [], set()
    for c in range(1, k + 1):
        off = c * step
        if off <= 0 or off >= n:
            break
        for i in range(n):
            j = (i + off) % n
            a, b = (i, j) if i < j else (j, i)
            if a == b or (a, b) in seen:
                continue
            seen.add((a, b))
            out.append((a, b))
            if len(out) >= budget:
                return out
    return out[:budget]


class SmartReactEngine:
    """把 SmartReact 的模板库包装成旧架构认识的 Engine。

    只实现 cascade/scorer 需要的两样：`.rules` 与 `.step()`。
    """

    def __init__(self,
                 default_max_products: int = 3,
                 max_products_per_pair: int = 32,
                 max_pairs: int = 4000,
                 fair_pairs: bool = False,
                 prefilter: bool = True,
                 verbose: bool = False,
                 gate_conditions: bool = True,
                 gate_tol_C: float = 30.0,
                 strict_redox_gate: bool = False,
                 extra_templates_path=None,
                 extra_template_min_support: int = 10,
                 extra_template_limit: int = 20000,
                 use_extra_templates: bool = True,
                 extra_requires_accepted_pair: bool = False,
                 medium_aware_reversibility: bool = True,
                 propagate_unclassified: bool = False,
                 use_mono_templates: bool = True,
                 mono_templates_path=None,
                 mono_include_co_reagent: bool = False,
                 mono_template_limit: int = 6000,
                 mono_redox_gate: bool = False,
                 use_curated_templates: bool = False,
                 use_mined_top_conditions: bool = False,
                 mined_top_limit: int = 100,
                 # ★ D5（2026-10-13）：3 组分正向模板。**默认关**——实测（甘草 12 成分、
                 #   2,443 条 arity=3 模板 × 200 个三元组）会把 6 s 的构建拖到 >400 s，
                 #   因为还没有「底物兼容性预筛」。要用请显式开（query_engine --triples）。
                 use_triple_templates: bool = False,
                 triple_templates_path=None,
                 max_triples: int = 200,
                 triple_min_support: int = 2,
                 triple_workers: int = 4):
        from smartreact import ReactionEnumerator

        self.default_max_products = default_max_products
        self.max_products_per_pair = max_products_per_pair
        self.max_pairs = max_pairs
        # ★ 2026-10-15：对子超预算时的截断方式。False=顺序截断（旧行为，默认不变）；
        #   True=公平截断（每个成分摊到大致相同的伙伴数，无"参与度冠军/陪跑"）。
        self.fair_pairs = bool(fair_pairs)
        # ★ 2026-10-15：底物兼容性预筛（默认关；见 reports/预筛设计-底物兼容性.md）
        self.prefilter = bool(prefilter)
        self._elem_cache: Dict[str, frozenset] = {}
        self._pf_checked = 0
        self._pf_skipped = 0
        self.verbose = verbose
        # ★ 条件门控（2026-10-11 第十轮）★
        #   背景：本文件 step() 原来的 docstring 写着「cond 目前不参与筛选，
        #   SmartReact 没有条件激活模型。按用户要求：条件只标注，不作为判据」。
        #   现在用户要求把它做起来 —— 用 ORD 抽出的 37 类真实条件（温度/溶剂）
        #   来判「这类反应在当前条件下会不会发生」。
        #   窗口来自 reports/conditions_normalized.json（tools/normalize_condition_table.py 产出）。
        self.gate_conditions = gate_conditions
        self.gate_tol_C = gate_tol_C
        # Strict redox gate: honour an explicitly stated atmosphere even when
        # no auxiliary reagents were supplied.  Off by default so benchmark
        # behaviour is unchanged.
        self.strict_redox_gate = bool(strict_redox_gate)
        self.cond_table = self._load_condition_table() if gate_conditions else {}
        # ★ C 试点：top mined 模板的 per-template 条件窗口
        self.mined_top_map: Dict[str, str] = {}
        self.mined_top_cond_table: Dict[str, Any] = {}
        self.extra_top_templates: list = []
        self.mono_top_templates: list = []
        self.mined_top_note = "未启用"
        if use_mined_top_conditions:
            self._load_mined_top_conditions(mined_top_limit)
        # ★ 第十二轮：必需试剂覆盖率（没有这个文件时自动退回"只降权不判零"的旧行为）★
        self.reagent_coverage = self._load_reagent_coverage() if gate_conditions else {}
        self.reagent_roles = self._compile_role_smarts()
        # ★ 第十五轮：可选加载【ORD 自抽的正向模板】★
        #   来源文件：reports/mined_forward_templates.jsonl（工具 tools/rdkit_template_lib.py）
        #   模板按支持数降序取前 N 个（与挖掘脚本同序，可复现）。
        # ★ 第十六轮（2026-10-13，用户拍板 B 案）：【默认开】★
        #   默认档 = K1 宽松档（支持>=1，limit=600 -> 编译通过 590 条）。
        #   ★ 第六十六轮（2026-10-15）：默认档已切"全量挖矿切片"（支持>=10、limit 3200；
        #     单底物切片 limit 1600）。复现旧 K1 档：显式传 extra_templates_path=旧文件
        #     + extra_template_min_support=1 + extra_template_limit=600。
        #   代价是实测的：HTE 召回 64.0% -> 69.2%，负例产物 1.38 -> 1.87/对（+36%），
        #   用户明确接受（证据：tools/hte_fpr_after_integration.py）。
        #   要复现「K1 关闭前」的旧基线数字 -> 显式传 use_extra_templates=False；
        #   要用保守档 K5 -> 传 extra_template_min_support=5。
        self.extra_templates = []
        self.extra_template_note = "未启用"
        self._extra_lib = None
        if (not use_extra_templates) or extra_templates_path is False:
            self.extra_template_note = "未启用（显式关闭）"
        else:
            _xt_path = (Path(extra_templates_path) if extra_templates_path
                        else DEFAULT_EXTRA_TEMPLATES)
            self.extra_templates, self.extra_template_note = self._load_extra_templates(
                _xt_path, extra_template_min_support, extra_template_limit)
        if self.mined_top_map and self.extra_templates:
            keep = []
            for sm, rx in self.extra_templates:
                name = self.mined_top_map.get(sm)
                if name:
                    self.extra_top_templates.append((sm, rx, name))
                else:
                    keep.append((sm, rx))
            self.extra_templates = keep
        self._extra_reqs = ([smarts_reactant_elems(sm) for sm, _rx in self.extra_templates]
                            if self.extra_templates else [])
        # ★ 第十七轮：自抽模板的「非孤儿」开关（默认关 = 保持第十六轮行为完全不变）★
        #   背景（实测）：mined_extra 不在 37 类条件表里 -> cond_activation() 走
        #   「无 ORD 条件数据，放行」分支返回 1.0，即它【完全绕过】温度/溶剂/必需试剂门控。
        #   本开关语义（我的建模选择，标【推断】不是实测）：
        #     「自抽模板只用于【丰富一个已被条件门控认可的（底物对, 条件）】，
        #       不能凭空创造一个 37 类门控认为不会发生的反应」
        #   即：同一底物对必须至少有一条 37 类结果通过门控，才允许追加 mined_extra 产物。
        self.extra_requires_accepted_pair = bool(extra_requires_accepted_pair)
        # ★ 第十九轮：介质相关可逆性（见 CONDENSATION_CLASSES 注释）。默认开；
        #   设 False 可退回"所有产物都不可逆"的旧行为（级联会重新出现分子量翻倍）。
        self.medium_aware_reversibility = bool(medium_aware_reversibility)
        # ★ 第十九轮：**无法判定可逆性的产物（如 mined_extra）默认不作为中间体传播**。
        #   理由（实测）：自抽模板的产物 `rule_name = "mined_extra"`，既不在 37 类里、
        #   也不在 CONDENSATION_CLASSES 里 → 介质可逆性判据管不到它 → 它照样一路传播，
        #   分子重原子 51→99→185→293→431→705→**1071**，单步耗时涨到 310 s（实测）。
        #   原则：**判不了可逆性，就不让它驱动多步**（产物仍照常出现在结果里，只是不当中间体）。
        #   想恢复旧行为（全都传播）-> propagate_unclassified=True。
        self.propagate_unclassified = bool(propagate_unclassified)
        # ★ 第二十二轮：单底物模板（水解/氧化/还原/消除…）—— 引擎原来只会把模板套在【底物对】上，
        #   单反应物模板根本无法使用；这里加载并按 arity=1 套用到每个底物。
        self.mono_templates = []
        self.mono_by_hint: Dict[Any, list] = {}
        self.mono_redox_gate = bool(mono_redox_gate)
        self.mono_template_note = "未启用"
        if use_mono_templates:
            _mp = (Path(mono_templates_path) if mono_templates_path
                   else DEFAULT_MONO_TEMPLATES)
            self.mono_by_hint, self.mono_template_note = self._load_mono_templates(
                _mp, mono_template_limit, mono_include_co_reagent)
            if self.mined_top_map:
                for k, lst in list(self.mono_by_hint.items()):
                    keep = []
                    for sm, rx in lst:
                        name = self.mined_top_map.get(sm)
                        if name:
                            self.mono_top_templates.append((sm, rx, name))
                        else:
                            keep.append((sm, rx))
                    self.mono_by_hint[k] = keep
                self.mono_templates = [t for sub in self.mono_by_hint.values() for t in sub]
            self.mono_templates = [t for sub in self.mono_by_hint.values() for t in sub]
        # ★ D5（2026-10-13）：3 组分模板（默认开；max_triples 给三元组组合数封顶，避免组合爆炸）
        self.triple_templates = []
        self.triple_template_note = "未启用"
        self.max_triples = int(max_triples)
        self.triple_workers = max(1, int(triple_workers))
        if use_triple_templates:
            _tp = (Path(triple_templates_path) if triple_templates_path
                   else DEFAULT_TRIPLE_TEMPLATES)
            self.triple_templates, self.triple_template_note = self._load_triple_templates(
                _tp, min_support=triple_min_support)
        # ★ B 试点：6 条 curated 规则（默认关，实时 chemreact.py 显式打开）
        self.curated_pair_templates = []
        self.curated_mono_templates = []
        self.curated_cond_table: Dict[str, Any] = {}
        self.curated_co_pool: Dict[str, list] = {}
        self.curated_note = "未启用"
        if use_curated_templates:
            self._load_curated_templates()
        self.gate_stats: Dict[str, Any] = {}

        t0 = time.time()
        self._enum = ReactionEnumerator()
        self._init_s: float = time.time() - t0

        meta = _load_reaction_names()
        evidence = _load_ord_evidence()

        # ★ 规则粒度 = 反应类型（37 条）
        # priority 用【ORD 里的复现次数】做数据驱动，不手写：
        #   log 压缩后线性映射到 [0.35, 0.90]，有证据的排前面
        rules: List[Dict[str, Any]] = []
        ev_max = max(evidence.values()) if evidence else 1
        for name in sorted(meta):
            ev = evidence.get(name, 0)
            if ev > 0:
                prio = 0.35 + 0.55 * (math.log1p(ev) / math.log1p(ev_max))
            else:
                prio = 0.35          # 无 ORD 证据 -> 最低档
            rules.append({
                "id": name,
                "name": name,
                "priority": round(prio, 4),
                "status": "ok",
                "n_templates": meta[name]["n_templates"],
                "categories": meta[name]["categories"],
                "ord_evidence": ev,
            })
        self.rules = rules
        self._rule_by_id = {r["id"]: r for r in rules}
        self.stats: Dict[str, Any] = {}

    # ---------------------------------------------------------------- 条件门控
    @staticmethod
    def _load_condition_table() -> Dict[str, Any]:
        """载入 ORD 规范化的条件表（37 类）。优先用规范化版，没有就退回原始版。"""
        import json
        for name in ("conditions_normalized.json", "conditions_by_reaction_type.json"):
            p = _STAGE / "reports" / name
            if p.exists():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
        return {}

    # ------------------------------------------------------- 必需试剂（第十二轮）
    @staticmethod
    def _load_reagent_coverage() -> Dict[str, Any]:
        """载入必需试剂覆盖率表；文件不存在 -> 空 dict（门控自动退回旧行为，不报错）。"""
        import json
        if not COVERAGE_TABLE.exists():
            return {}
        try:
            return json.loads(COVERAGE_TABLE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_lib(self):
        """按【显式文件路径】加载 tools/rdkit_template_lib.py（单一真相）。

        用 importlib 避免把 staging/tools 塞进 sys.path（tools 里有 probe.py 这类通用名，会遮蔽）。
        """
        if getattr(self, "_extra_lib", None) is not None:
            return self._extra_lib
        import importlib.util
        import sys as _sys
        lib_py = _STAGE / "tools" / "rdkit_template_lib.py"
        if not lib_py.exists():
            return None
        spec = importlib.util.spec_from_file_location("rdkit_template_lib", lib_py)
        mod = importlib.util.module_from_spec(spec)
        # ★ 必须先注册进 sys.modules 再 exec_module ★
        #   否则模块内 @dataclass 会因为 sys.modules[cls.__module__] 是 None 而报
        #   AttributeError: 'NoneType' object has no attribute '__dict__'（实测踩到）
        _sys.modules["rdkit_template_lib"] = mod
        spec.loader.exec_module(mod)
        self._extra_lib = mod
        return mod

    def _load_mined_top_conditions(self, limit: int):
        """加载 top mined 模板的 per-template 条件窗口（来自 ORD 实测）。"""
        import json
        if not MINED_TOP_CONDITIONS.exists():
            self.mined_top_note = "缺 %s" % MINED_TOP_CONDITIONS.name
            return
        try:
            rows = (json.loads(MINED_TOP_CONDITIONS.read_text(encoding="utf-8"))
                    .get("rows") or [])
        except Exception as ex:                    # noqa: BLE001
            self.mined_top_note = "读取失败：%s" % ex
            return
        n = 0
        for i, row in enumerate(rows[:max(1, int(limit))], 1):
            sm = str(row.get("template") or "")
            if not sm:
                continue
            name = "mined_top_%03d" % i
            self.mined_top_map[sm] = name
            tmin = row.get("temps_min")
            tmax = row.get("temps_max")
            self.mined_top_cond_table[name] = {
                "n_ord_matched": int(row.get("match") or 0),
                "solvents": list((row.get("solvents") or {}).keys()),
                "catalysts": list((row.get("catalysts") or {}).keys()),
                "reagents": [],
                "auxiliary_reagents": [],
                "temp_C": ({"min": tmin, "max": tmax, "median": None,
                            "n": int(row.get("n_temp") or 0)}
                           if tmin is not None and tmax is not None else None),
                "time_min": None,
                "ph": None,
            }
            n += 1
        self.mined_top_note = "top mined: %d 条（limit %d）" % (n, limit)

    def _load_curated_templates(self):
        """加载 6 条 curated 规则为带 reaction_name 的单/双底物模板。"""
        import json
        from rdkit.Chem import rdChemReactions
        p = _STAGE / "rules" / "rules.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as ex:                    # noqa: BLE001
            self.curated_note = "读取 rules.json 失败：%s" % ex
            return
        profiles = data.get("profiles") or {}
        n_pair = n_mono = n_fail = 0
        for r in data.get("rules") or []:
            rid = r.get("id")
            # Load every rule the rulebook marks active.  The hard-coded
            # CURATED_RULE_IDS list used to gate this down to six entries, which
            # silently excluded glycoside hydrolysis, ester hydrolysis, Maillard
            # and most other transformations a decoction actually undergoes.
            if str(r.get("status") or "active") != "active":
                continue
            sm = str(r.get("smarts") or "")
            try:
                rx = rdChemReactions.ReactionFromSmarts(sm)
            except Exception:
                n_fail += 1
                continue
            if rx is None:
                n_fail += 1
                continue
            n_tpl = rx.GetNumReactantTemplates()
            if n_tpl == 1:
                self.curated_mono_templates.append((sm, rx, rid))
                n_mono += 1
            elif n_tpl == 2:
                self.curated_pair_templates.append((sm, rx, rid))
                n_pair += 1
            else:
                n_fail += 1
                continue
            prof = profiles.get(r.get("condition_profile")) or {}
            temp = prof.get("temperature") or {}
            time_min = prof.get("time_min") or {}
            self.curated_cond_table[rid] = {
                "n_ord_matched": 0,
                "solvents": list(prof.get("solvent") or []),
                "catalysts": list(prof.get("catalyst") or []),
                "atmospheres": list(prof.get("atmosphere") or []),
                "reagents": [],
                "auxiliary_reagents": [],
                "temp_C": ({"min": temp.get("min"), "max": temp.get("max"),
                            "median": temp.get("default"), "n": 0}
                           if temp else None),
                "time_min": ({"min": time_min.get("min"),
                              "max": time_min.get("max"),
                              "median": time_min.get("default"), "n": 0}
                             if time_min else None),
                "ph": prof.get("pH"),
            }
            pool = []
            for c in r.get("co_substrate_pool") or []:
                smi = str(c.get("smiles") or "").strip()
                if smi:
                    pool.append({"smiles": smi,
                                 "when_solvent": c.get("when_solvent") or []})
            self.curated_co_pool[rid] = pool
        self.curated_note = ("curated: 双底物 %d / 单底物 %d / 失败 %d"
                             % (n_pair, n_mono, n_fail))

    def _load_extra_templates(self, path, min_support: int, limit: int):
        mod = self._load_lib()
        if mod is None:
            return [], f"跳过：找不到 {_STAGE / 'tools' / 'rdkit_template_lib.py'}"
        try:
            tpls = mod.load_mined_templates(Path(path), min_support=min_support, limit=limit)
            compiled, n_fail, n_arity, hist = mod.compile_templates_report(tpls)
        except Exception as e:
            # ★ 默认开之后这条路必须能救命 ★
            #   模板文件缺失/损坏时退回「无额外模板」，但把原因写进 note（不静默），
            #   不要让整个引擎因为一个可选增强而起不来。
            return [], f"跳过：加载失败（{type(e).__name__}: {e}）"
        return compiled, (f"启用：加载 {len(tpls)} 条（支持>={min_support}），"
                          f"编译通过 {len(compiled)}，编译失败 {n_fail}，"
                          f"★元数≠2 丢弃 {n_arity} 条（arity 分布 "
                          f"{dict(sorted(hist.items()))}）")

    def _load_mono_templates(self, path, limit: int, include_co_reagent: bool):
        """加载【单底物】模板（第二十二轮）：只取 arity=1，默认剔除"需共试剂"的那些。

        需要共试剂（产物侧有未映射重原子，如甲酯化里的甲醇甲基）的模板**直接套用会凭空造产物**
        → 默认不启用，留给"条件层"（试剂在不在）门控。见 rdkit_template_lib.needs_co_reagent。
        """
        mod = self._load_lib()
        if mod is None:
            return {}, "跳过：找不到 rdkit_template_lib.py"
        try:
            tpls = mod.load_mined_templates(Path(path), min_support=1, limit=limit)
            by, n_fail = mod.compile_templates_all(tpls)
        except Exception as e:
            return {}, f"跳过：加载失败（{type(e).__name__}: {e}）"
        one = by.get(1, [])
        # ★ D5：把「元数≥2 被丢弃」显式报出来（旧版本是静默丢的）
        n_ge2 = sum(len(v) for k, v in by.items() if int(k) >= 2)
        buckets: Dict[Any, list] = {None: [], "reduce": [], "oxidize": []}
        dropped = 0
        for sm, rx in one:
            if mod.needs_co_reagent(sm) is True and not include_co_reagent:
                dropped += 1
                continue
            hint = mod.redox_hint(sm)
            buckets.setdefault(hint, []).append((sm, rx))
        n_keep = sum(len(v) for v in buckets.values())
        return buckets, (f"启用：加载 {len(tpls)} 条 -> arity=1 共 {len(one)} 条，"
                         f"保留 {n_keep}（需共试剂的{'含' if include_co_reagent else '不含'}，"
                         f"按需共试剂剔除 {dropped}）；"
                         f"隐含环境：不需氧化还原 {len(buckets.get(None, []))}、"
                         f"需还原 {len(buckets.get('reduce', []))}、"
                         f"需氧化 {len(buckets.get('oxidize', []))}，编译失败 {n_fail}；"
                         f"★元数≥2 丢弃 {n_ge2} 条（arity 分布 "
                         f"{dict(sorted((int(k), len(v)) for k, v in by.items()))}）")

    def _load_triple_templates(self, path, min_support: int = 1):
        """★ D5（2026-10-13）：加载【3 反应物】正向模板（`tools/mine_3c_templates.py` 产出）。

        口径：只取 arity==3（其它元数交给别的路径）；不按共试剂过滤（3 组分模板本身就带第三个组分）。
        """
        mod = self._load_lib()
        if mod is None:
            return [], "跳过：找不到 rdkit_template_lib.py"
        if not Path(path).exists():
            return [], f"跳过：文件不存在 {path}"
        try:
            tpls = mod.load_mined_templates(Path(path), min_support=int(min_support), limit=None)
        except Exception as e:                       # noqa: BLE001 —— 不静默：写进 note
            return [], f"跳过：加载失败（{type(e).__name__}: {e}）"
        from rdkit.Chem import rdChemReactions
        three, n_fail, hist = [], 0, {}
        for t in tpls:
            try:
                rx = rdChemReactions.ReactionFromSmarts(t.smarts)
            except Exception:
                n_fail += 1
                continue
            if rx is None:
                n_fail += 1
                continue
            a = int(rx.GetNumReactantTemplates())
            hist[a] = hist.get(a, 0) + 1
            if a != 3:
                continue
            # ★ 带上 support：产物要按"这条套路见过几次"打标记（用户要求：只打标记、不删产物）
            three.append((t.smarts, rx, int(t.support)))
        return three, (f"启用：加载 {len(tpls)} 条（support>={min_support}）-> arity=3 共 {len(three)} 条"

                       f"（arity 分布 {hist}，编译失败 {n_fail}）")

    def _mono_allowed(self, cond):
        """按当前条件筛出【可套用】的单底物模板（见 REDUCTANT_HINTS 一带的注释）。

        门控关 / cond 为 None -> 不过滤（退回第二十三轮行为）。
        """
        if not self.mono_redox_gate or cond is None:
            return self.mono_templates
        atm = str(getattr(cond, "atmosphere", "") or "").lower()
        reagents = " ".join(str(r) for r in (getattr(cond, "reagents", ()) or ()))
        # ★ 原则：**信息缺失 != 信息否定** —— 条件里一个试剂都没写时，不能因为"气氛是空气"就断定
        #   没有还原剂（ORD 表试剂可得率 0% 的教训，见第二十四轮）。此时不过滤。
        if not reagents.strip():
            if not self.strict_redox_gate:
                self.gate_stats["单底物模板_无试剂信息_不门控"] = 1
                return self.mono_templates
            # Strict mode: the atmosphere alone is enough to rule a redox
            # class in or out.  Air excludes reduction, H2 excludes oxidation.
            self.gate_stats["单底物模板_严格气氛门控"] = 1
        reducing = atm in REDUCING_ATMOS or any(h in reagents for h in REDUCTANT_HINTS)
        oxidizing = atm in OXIDIZING_ATMOS or any(h in reagents for h in OXIDANT_HINTS)
        n_red = len(self.mono_by_hint.get("reduce", []))
        n_oxi = len(self.mono_by_hint.get("oxidize", []))
        # 统计口径：本次 step 因气氛而【未启用】的模板数（幂等，不按 chunk 累加）
        self.gate_stats["单底物模板_因气氛跳过_需还原"] = 0 if reducing else n_red
        self.gate_stats["单底物模板_因气氛跳过_需氧化"] = 0 if oxidizing else n_oxi
        out = list(self.mono_by_hint.get(None, []))
        if reducing:
            out += self.mono_by_hint.get("reduce", [])
        if oxidizing:
            out += self.mono_by_hint.get("oxidize", [])
        return out

    def _medium_reversible(self, reaction_name: str, cond) -> bool:
        """水相介质里的脱水缩合类 -> 可逆（不参与级联传播）。见表 CONSTANT 注释。

        ★ 建模选择，不是 ORD 实测值；只在溶剂粗类别为 water/aqueous 时生效。
        """
        if not self.medium_aware_reversibility:
            return False
        if reaction_name not in CONDENSATION_CLASSES:
            return False
        if cond is None:
            return False
        try:
            sc = solvent_class(getattr(cond, "solvent", "") or "")
        except Exception:
            return False
        return sc in ("water", "aqueous")

    def _nonpropagating(self, reaction_name: str, cond) -> bool:
        """这个产物该不该被标为"不传播"？两条判据（见 __init__ 注释）：

          ① 介质相关：水相里的脱水缩合类 -> 可逆
          ② 判不了就保守：不在 37 类里的产物（如 `mined_extra`）默认不传播
        """
        if reaction_name not in self._rule_by_id and not self.propagate_unclassified:
            return True
        return self._medium_reversible(reaction_name, cond)

    def _elems_of(self, cs: str):
        e = self._elem_cache.get(cs)
        if e is None:
            m = get_mol(cs)
            e = frozenset(a.GetSymbol() for a in m.GetAtoms()) if m is not None else frozenset()
            self._elem_cache[cs] = e
        return e

    def _prefilter_pairs(self, sa: str, sb: str):
        """元素门 + 角色分派；返回 (过滤后的 (sm, rx) 列表, 跳过条数)。fail-open 项永不剔除。"""
        ea, eb = self._elems_of(sa), self._elems_of(sb)
        keep, skipped = [], 0
        for (sm, rx), rq in zip(self.extra_templates, self._extra_reqs):
            if rq is None:
                keep.append((sm, rx))
                continue
            if len(rq) == 1:
                ok = rq[0] <= (ea | eb)
            else:
                ok = ((rq[0] <= ea and rq[1] <= eb) or (rq[0] <= eb and rq[1] <= ea))
            if ok:
                keep.append((sm, rx))
            else:
                skipped += 1
        return keep, skipped


    def _extra_results(self, chunk, subs, cond=None):
        """对这批底物对跑额外模板；并跑【单底物】模板（第二十二/二十四轮，按条件筛）。"""
        from smartreact.types import ReactionResult
        lib = getattr(self, "_extra_lib", None)
        if lib is None and (self.curated_pair_templates or self.curated_mono_templates):
            lib = self._load_lib()
            self._extra_lib = lib
        if lib is None:
            return []
        out = []
        # ---- 双底物模板（mined_extra）----
        if self.extra_templates:
            for i, j in chunk:
                sa, sb = subs[i][1], subs[j][1]
                try:
                    if self.prefilter and self._extra_reqs:
                        tpls, sk = self._prefilter_pairs(sa, sb)
                        self._pf_checked += len(self.extra_templates)
                        self._pf_skipped += sk
                    else:
                        tpls = self.extra_templates
                    got = lib.apply_pair(tpls, get_mol(sa), get_mol(sb))
                except Exception:
                    k = "extra模板_套用异常"
                    self.gate_stats[k] = self.gate_stats.get(k, 0) + 1
                    continue
                if got:
                    out.append(ReactionResult(reactant_a=sa, reactant_b=sb,
                                              reaction_name="mined_extra",
                                              products=sorted(got)))
        # ---- 单底物模板（mined_mono）：对本批出现过的【每个不同底物】各套一次 ----
        # ★ chunk 为空（没有底物对，例如单底物输入）时就对全部底物套用 ★
        if self.mono_templates:
            uniq = (sorted({k for pair in chunk for k in pair}) if chunk
                    else list(range(len(subs))))
            mono_use = self._mono_allowed(cond)
            for k in uniq:
                sa = subs[k][1]
                try:
                    got = lib.apply_single(mono_use, get_mol(sa))
                except Exception:
                    key = "单底物模板_套用异常"
                    self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                    continue
                if got:
                    # reactant_b 传同一个分子：step() 靠 reactant_a/b 反查来源 Compound，单底物也用这个路径
                    out.append(ReactionResult(reactant_a=sa, reactant_b=sa,
                                              reaction_name="mined_mono",
                                              products=sorted(got)))
        # ---- ★ C 试点：top mined 模板（per-template 条件名）----
        if self.extra_top_templates:
            for i, j in chunk:
                sa, sb = subs[i][1], subs[j][1]
                for sm, rx, name in self.extra_top_templates:
                    try:
                        got = lib.apply_pair([(sm, rx)], get_mol(sa), get_mol(sb))
                    except Exception:
                        key = "mined_top双底物_套用异常"
                        self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                        continue
                    if got:
                        out.append(ReactionResult(
                            reactant_a=sa, reactant_b=sb, reaction_name=name,
                            products=sorted(got)[:max(1, self.max_products_per_pair)]))
        if self.mono_top_templates:
            uniq_t = (sorted({k for pair in chunk for k in pair}) if chunk
                      else list(range(len(subs))))
            for k in uniq_t:
                sa = subs[k][1]
                for sm, rx, name in self.mono_top_templates:
                    try:
                        got = lib.apply_single([(sm, rx)], get_mol(sa))
                    except Exception:
                        key = "mined_top单底物_套用异常"
                        self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                        continue
                    if got:
                        out.append(ReactionResult(
                            reactant_a=sa, reactant_b=sa, reaction_name=name,
                            products=sorted(got)[:max(1, self.max_products_per_pair)]))
        # ---- ★ B 试点：6 条 curated 规则（带 reaction_name）----
        if self.curated_pair_templates:
            for i, j in chunk:
                sa, sb = subs[i][1], subs[j][1]
                for sm, rx, name in self.curated_pair_templates:
                    try:
                        got = lib.apply_pair([(sm, rx)], get_mol(sa), get_mol(sb))
                    except Exception:
                        key = "curated双底物_套用异常"
                        self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                        continue
                    if got:
                        out.append(ReactionResult(
                            reactant_a=sa, reactant_b=sb,
                            reaction_name=name,
                            products=sorted(got)[:max(1, self.max_products_per_pair)]))
            # 单输入 + 条件允许的 co_substrate_pool（乙醇/硫醇/葡萄糖等）
            for k in range(len(subs)):
                sa = subs[k][1]
                for sm, rx, name in self.curated_pair_templates:
                    for co in self._curated_co_smiles(name, cond):
                        if not co or co == sa:
                            continue
                        for x, y in ((sa, co), (co, sa)):
                            try:
                                got = lib.apply_pair([(sm, rx)],
                                                     get_mol(x), get_mol(y))
                            except Exception:
                                key = "curated共底物_套用异常"
                                self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                                continue
                            if got:
                                out.append(ReactionResult(
                                    reactant_a=x, reactant_b=y,
                                    reaction_name=name,
                                    products=sorted(got)[:max(1, self.max_products_per_pair)]))
        if self.curated_mono_templates:
            uniq_c = (sorted({k for pair in chunk for k in pair}) if chunk
                      else list(range(len(subs))))
            for k in uniq_c:
                sa = subs[k][1]
                for sm, rx, name in self.curated_mono_templates:
                    if self.strict_redox_gate:
                        allowed = ((self.curated_cond_table.get(name) or {})
                                   .get("atmospheres") or [])
                        atm = str(getattr(cond, "atmosphere", "") or "").lower()
                        if allowed and atm and atm not in [
                                str(a).lower() for a in allowed]:
                            self.gate_stats["curated_单底物_气氛不符"] = (
                                self.gate_stats.get("curated_单底物_气氛不符", 0) + 1)
                            continue
                    try:
                        got = lib.apply_single([(sm, rx)], get_mol(sa))
                    except Exception:
                        key = "curated单底物_套用异常"
                        self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                        continue
                    if got:
                        out.append(ReactionResult(
                            reactant_a=sa, reactant_b=sa,
                            reaction_name=name,
                            products=sorted(got)[:max(1, self.max_products_per_pair)]))
        # ---- ★ D5（2026-10-13）3 组分模板：对 chunk 里出现过的底物取三元组（有上限）----
        #   用户选了方案 C：**全量模板 + 多进程**（不改化学判据，只是同时开几口锅），
        #   并且给"只见过一次的套路"产出的东西**打标记**（support 带在 product_support 里）。
        if self.triple_templates and self.max_triples:
            from itertools import combinations
            uniq_t = (sorted({k for pair in chunk for k in pair}) if chunk
                      else list(range(len(subs))))
            combos = list(combinations(uniq_t, 3))
            if len(combos) > self.max_triples:
                k = "三组分模板_组合被截断"
                self.gate_stats[k] = self.gate_stats.get(k, 0) + (len(combos) - self.max_triples)
                combos = combos[:self.max_triples]
            smi_triples = [(subs[a][1], subs[b][1], subs[c][1]) for (a, b, c) in combos]
            smarts_support = [(sm, sup) for (sm, _rx, sup) in self.triple_templates]
            got_list: list = []
            done = False
            if self.triple_workers > 1 and len(smi_triples) > 1:
                try:
                    from concurrent.futures import ProcessPoolExecutor
                    nw = min(self.triple_workers, len(smi_triples))
                    step = (len(smi_triples) + nw - 1) // nw
                    batches = [smi_triples[i:i + step]
                               for i in range(0, len(smi_triples), step)]
                    with ProcessPoolExecutor(max_workers=nw,
                                             initializer=_triple_worker_init,
                                             initargs=(smarts_support,)) as ex:
                        for res in ex.map(_triple_worker, batches):
                            got_list.extend(res)
                    self.gate_stats["三组分模板_并行进程数"] = nw
                    done = True
                except Exception as ex:              # noqa: BLE001 —— 并行失败退回串行，但要说话
                    self.gate_stats["三组分模板_并行失败_退回串行"] = 1
                    print(f"   [warn] 三组分并行失败，退回串行：{type(ex).__name__}: {ex}")
            if not done:
                _triple_worker_init(smarts_support)
                got_list = _triple_worker(smi_triples)
            for (sa, sb, sc, got) in got_list:
                out.append(ReactionResult(reactant_a=sa, reactant_b=sb, reactant_c=sc,
                                          reaction_name="mined_triple",
                                          products=sorted(got), product_support=got))
        return out

    def _curated_co_smiles(self, rule_name: str, cond) -> list:
        """按当前溶剂过滤 co_substrate_pool（溶剂族比较，不要求字面相同）。"""
        pool = self.curated_co_pool.get(rule_name) or []
        if not pool:
            return []
        if cond is None:
            return [c["smiles"] for c in pool]
        sc = solvent_class(getattr(cond, "solvent", "") or "")
        out = []
        for c in pool:
            ws = c.get("when_solvent") or []
            if ws and not any(solvent_class(w) == sc for w in ws):
                continue
            out.append(c["smiles"])
        return out

    @staticmethod
    def _compile_role_smarts():
        """预编译角色 SMARTS。编译失败的角色直接丢掉并留痕（不静默）。"""
        from rdkit import Chem
        out = []
        for name, smarts in REAGENT_ROLE_SMARTS:
            patt = Chem.MolFromSmarts(smarts)
            if patt is None:
                print(f"[warn] 角色 SMARTS 编译失败，已忽略: {name} {smarts}")
                continue
            out.append((name, patt))
        return tuple(out)

    def _role_of(self, smiles: str):
        """这个试剂属于哪个功能角色？（都不匹配返回 None）"""
        from rdkit import Chem
        m = Chem.MolFromSmiles(smiles)
        if m is None:
            return None
        for name, patt in self.reagent_roles:
            try:
                if m.HasSubstructMatch(patt):
                    return name
            except Exception:
                continue
        return None

    def required_reagent_units(self, reaction_name: str, entry: Dict[str, Any]):
        """这类反应的"必需件"清单（每个必需件可能含多个同功能成员）。

        规则（全部基于实测覆盖率，角色归并是建模选择）：
          - 单分子覆盖率 >= REQUIRED_COV -> 必需件（成员就它自己）
          - 同角色成员覆盖率【相加】>= REQUIRED_COV -> 合并成一个必需件
          - 与溶剂同名的（ORD 把 water 之类写进 auxiliary_reagents）先剔除，避免误杀
        """
        cov = self.reagent_coverage.get(reaction_name)
        if not cov or int(cov.get("n_reactions", 0)) < REQUIRED_MIN_N:
            return []
        # 剔除本身就是溶剂/催化剂的"伪试剂"
        solvent_keys = {self._reagent_key(s) for s in (entry.get("solvents") or [])}
        solvent_keys.discard("")
        # ★ 角色归并要看 required + optional 两边 ★
        #   实测教训：DEAD 0.279 / DIAD 0.233 单看都不到 0.5（在 optional 桶里），
        #   只从 required 桶取 -> 偶氮二羧酸酯角色永远凑不够 0.5 -> "缺 DEAD 判零"落不了地。
        def _ok(r):
            return (r.get("smiles") and r["smiles"] not in solvent_keys
                    and not self._is_ion_fragment(r["smiles"]))

        required = [r for r in (cov.get("required") or []) if _ok(r)]
        optional = [r for r in (cov.get("optional") or []) if _ok(r)]
        by_role: Dict[str, Dict[str, Any]] = {}
        singles: List[Dict[str, Any]] = []
        for r in required + optional:
            role = self._role_of(r["smiles"])
            if role:
                u = by_role.setdefault(role, {"name": role, "members": [],
                                              "coverage": 0.0, "n": cov["n_reactions"]})
                u["members"].append(r["smiles"])
                u["coverage"] += float(r["coverage"])
        for r in required:      # 单分子必需件只认 required 桶（个体覆盖率 >= 阈值）
            if not self._role_of(r["smiles"]):
                singles.append({"name": r["smiles"], "members": [r["smiles"]],
                                "coverage": float(r["coverage"]),
                                "n": cov["n_reactions"]})
        units = [u for u in by_role.values() if u["coverage"] >= REQUIRED_COV]
        for u in units:
            u["coverage"] = min(1.0, u["coverage"])
        return singles + units

    # ★ 常见辅助试剂的名字 -> SMILES ★
    #   实测必要性：ORD 条件表里存的是**名字**（'triphenylphosphine'），
    #   而调用方习惯给 SMILES（P(c1ccccc1)(c1ccccc1)c1ccccc1）。
    #   MolFromSmiles('triphenylphosphine') 返回 None -> 匹配必然失败（踩过）。
    REAGENT_ALIAS = {
        "triphenylphosphine": "P(c1ccccc1)(c1ccccc1)c1ccccc1",
        "tributylphosphine": "CCCCP(CCCC)CCCC",
        "diethyl azodicarboxylate": "CCOC(=O)/N=N/C(=O)OCC",
        "dead": "CCOC(=O)/N=N/C(=O)OCC",
        "diisopropyl azodicarboxylate": "CC(C)OC(=O)/N=N/C(=O)OC(C)C",
        "triethylamine": "CCN(CC)CC",
        "et3n": "CCN(CC)CC",
        "dipea": "CC(C)N(C(C)C)C(C)C",
        "diisopropylethylamine": "CC(C)N(C(C)C)C(C)C",
        "pyridine": "c1ccncc1",
        "sodium hydride": "[NaH]",
        "nah": "[NaH]",
        "potassium carbonate": "O=C([O-])[O-].[K+].[K+]",
        "k2co3": "O=C([O-])[O-].[K+].[K+]",
        "sodium carbonate": "O=C([O-])[O-].[Na+].[Na+]",
        "na2co3": "O=C([O-])[O-].[Na+].[Na+]",
        "cesium carbonate": "O=C([O-])[O-].[Cs+].[Cs+]",
        "cs2co3": "O=C([O-])[O-].[Cs+].[Cs+]",
        "hatu": "CN(C)C(=[N+](C)C)On1nnc2ccccc21",
        # ★ 第十二轮修正两处手写 SMILES 错误（实测：canonical 分子式不对）★
        #   原 "hobt": "O=Nn1nnc2ccccc21" 是苯并三唑 N-氧化物(C6H4N4O)，不是 HOBt(C6H5N3O)；
        #      正确结构 = 1-羟基苯并三唑。
        #   原 "dcc"/"dicyclohexylcarbodiimide": "N#CN=C1CCCCC1" 是异腈-亚胺(C7H10N2)，
        #      DCC 是 N,N'-二环己基碳二亚胺(C13H22N2)。
        #   为什么要紧：必需试剂判据现在会【判零】，别名错 -> 用户按名字给试剂时匹配不上 -> 误杀。
        #   核对脚本：tools/probe_reagent_roles.py
        "hobt": "On1nnc2ccccc21",
        "dcc": "C1CCCCC1N=C=NC1CCCCC1",
        "dicyclohexylcarbodiimide": "C1CCCCC1N=C=NC1CCCCC1",
        "dmap": "CN(C)c1ccncc1",
        "4-dimethylaminopyridine": "CN(C)c1ccncc1",
        "sodium triacetoxyborohydride": "CC(=O)O[BH-](OC(C)=O)OC(C)=O.[Na+]",
        "sodium cyanoborohydride": "[BH3-]C#N.[Na+]",
        "acetic acid": "CC(=O)O",
        "hydrochloric acid": "Cl",
        "hcl": "Cl",
        "sulfuric acid": "OS(=O)(=O)O",
        "thionyl chloride": "O=S(Cl)Cl",
        "water": "O",
    }

    def _reagent_key(self, s: str) -> str:
        """把试剂（SMILES 或名字）归一成可比较的 key。"""
        if not s:
            return ""
        raw = str(s).strip()
        # 1) 名字别名
        alias = self.REAGENT_ALIAS.get(raw.lower().replace(" ", "").replace("-", ""))
        #   别名表里也存了去空格/连字符的形式，两种都试
        if alias is None:
            alias = self.REAGENT_ALIAS.get(raw.lower())
        cand = alias or raw
        # 2) SMILES 规范化（★ 去立体：DEAD 的 "/N=N/" 与 "N=N" 必须算同一个试剂，
        #    否则覆盖率/匹配都会把同一个试剂拆成两半 —— 实测见
        #    tools/probe_canon_variants.py 与 extract_aux_reagent_coverage.canon_nomap）
        try:
            from rdkit import Chem
            m = Chem.MolFromSmiles(cand)
            if m is not None:
                for a in m.GetAtoms():
                    a.SetAtomMapNum(0)
                return Chem.MolToSmiles(m, isomericSmiles=False)
        except Exception:
            pass
        # 3) 退回名字（小写去符号）
        return raw.lower().replace(" ", "").replace("-", "")

    def _reagent_match(self, want: str, got: str, allow_role: bool = False) -> bool:
        """两个辅助试剂是不是同一个东西？名字/SMILES 都能比。

        ★ 第十二轮：加"组分级"比较 ★
        原因（实测）：ORD 的 CXSMILES 把盐按 "." 拆开，K2CO3 变成
        "O=C([O-])[O-]" + "[K+]" 两条独立记录，覆盖率表里存的是碎片；
        而调用方给的 "O=C([O-])[O-].[K+].[K+]" 是整分子 -> 整串比较必然不相等 -> 误判"缺试剂"。
        现在：整串相等，或**任一组件相等**，都算匹配。

        ★ 第三十四轮：加"角色级"比较（`allow_role=True`）★
        原因（实测，第三十三轮诊断）：条件表里"常用辅助试剂"存的是**6 个老名字**
        （triethylamine / K2CO3 / Cs2CO3 / DIPEA / water / NaOtBu），
        而真实文献用的是**同一角色的现代试剂**（tBuXPhos-Pd-G3、tAmOK、LiHMDS…）。
        字面比较必然全部落空 -> 一条 0.5 的常数惩罚盖住 82% 的记录 -> 判别力归零。
        角色级比较 = "同为金属催化剂 / 同为碱 / 同为膦配体 / 同为水"就认。
        ★ 只用于**降权**那一路；【必需试剂判零】那条路（allow_role 默认 False）**不放宽** ★
        """
        kw, kg = self._reagent_key(want), self._reagent_key(got)
        if not kw or not kg:
            return False
        if kw == kg:
            return True
        pw = {p for p in kw.split(".") if p}
        pg = {p for p in kg.split(".") if p}
        if pw & pg:
            return True
        if allow_role:
            rw, rg = self._reagent_role(want), self._reagent_role(got)
            if rw and rw == rg:
                return True
        return False

    # ★ 角色词表（第三十四轮）：通用有机化学的功能基团/催化剂类别，不是某个场景专用。
    #   顺序有意义：先判金属催化剂（Pd(PPh3)4 里也有 P，但它是催化剂不是配体）。
    _ROLE_TOKENS = (
        ("metal_catalyst", ("pd", "pt", "ni", "cu", "ru", "rh", "ir", "fe", "co",
                            "palladium", "nickel", "copper", "platinum", "ruthenium",
                            "iron", "cobalt", "iridium", "rhodium",
                            "dba", "oac", "acac", "g3", "g4", "xphos", "sphos",
                            "brettphos", "ruphos", "jackiephos", "binap", "dppf",
                            "xantphos", "bipyphos", "pph3", "p(t-bu)3", "tbuxphos",
                            "ad2n", "cataxium", "sk-cc", "p2et", "p(tbu)3")),
        ("phosphine_ligand", ("phosphine", "phospine", "pph3", "xphos", "sphos",
                              "brettphos", "ruphos", "jackiephos", "binap", "dppf",
                              "xantphos", "davephos", "tbuphos", "cyjohnphos",
                              "p(t-bu)3", "p(tbu)3", "tri-tert-butylphosphine",
                              "tricyclohexylphosphine", "bipyphos")),
        ("carbonate_base", ("carbonate", "cs2co3", "k2co3", "na2co3", "caco3",
                            "li2co3", "khco3", "nahco3", "csco3")),
        ("alkoxide_base", ("tert-butoxide", "t-butoxide", "tbutoxide", "otbu",
                           "ot-bu", "otam", "amok", "oet", "ome", "methoxide",
                           "ethoxide", "propoxide", "liotbu", "naotbu", "kotbu",
                           "tamok", "naome", "naoet", "koet", "lihmds", "khmds",
                           "nahmds", "hmds", "lda", "lihmd")),
        ("amine_base", ("triethylamine", "dipea", "hünig", "hunig", "et3n", "et3n",
                        "tmeda", "dbu", "mtbd", "dabco", "pyridine", "lutidine",
                        "collidine", "n-methylmorpholine", "nmm", "tmG", "tmg",
                        "btmg", "proton sponge", "diisopropylethylamine",
                        "diisopropylamine", "morpholine", "piperidine", "aniline")),
        ("phosphate_base", ("phosphate", "k3po4", "cs3po4", "na3po4", "k2hpo4",
                            "kh2po4", "btpp")),
        ("water", ("water", "h2o", "aqueous")),
        ("acid", ("acid", "hcl", "tfa", "acetic", "sulfuric", "tosic", "msa",
                  "triflic", "h2so4", "h3po4", "formic")),
        ("hydride_reductant", ("nabh4", "libh4", "kbh4", "lialh4", "lah",
                               "dibal", "dibal-h", "sodium borohydride",
                               "sodium cyanoborohydride", "cyanoborohydride",
                               "hantzsch", "et3sih", "pmhs", "hydrogen")),
        ("azodicarboxylate", ("dead", "diad", "dead", "azodicarboxylate",
                              "diethyl azodicarboxylate", "diisopropyl azodicarboxylate")),
    )
    _ROLE_CACHE: Dict[str, str] = {}

    def _reagent_role(self, s: str) -> str:
        """试剂（名字或 SMILES）-> 功能角色；认不出返回 ""（宁可不认，不硬猜）。"""
        if not s:
            return ""
        raw = str(s).strip()
        if raw in self._ROLE_CACHE:
            return self._ROLE_CACHE[raw]
        t = raw.lower().replace(" ", "").replace("-", "").replace("_", "")
        role = ""
        for name, toks in self._ROLE_TOKENS:
            for tok in toks:
                tk = tok.replace(" ", "").replace("-", "").replace("_", "")
                if tk and tk in t:
                    role = name
                    break
            if role:
                break
        self._ROLE_CACHE[raw] = role
        return role

    def _is_ion_fragment(self, smiles: str) -> bool:
        """单原子碎片（[Na+]/[K+]/[Cs+]/[H-]/[Mg]/[Cl-]…）= 反离子，不是"必需试剂"。

        实测（tools/probe_coverage_entries.py）：覆盖率表里 required 出现最多的是
        [Na+](13 处)/[K+](11 处)/[Cs+](6 处) —— 它们只是碱的配对离子，
        若当成必需件，会给"缺 K+ 判零"这种荒谬判据。
        """
        from rdkit import Chem
        m = Chem.MolFromSmiles(smiles)
        return m is not None and m.GetNumAtoms() <= 1

    def cond_activation(self, reaction_name: str, cond) -> Tuple[float, str]:
        """这条反应类型在当前条件下会不会发生？返回 (分数 0~1, 原因)。

        判据（全部来自 ORD 实测条件分布，不手写）：
          1. 温度：超出 [min, max] 太多 -> 判零；窗口内 -> 1.0；边界外 tolerance 内 -> 线性衰减
             （容差存在的原因：ORD 的条件分布是"实际做过的"，不是物理边界）
          2. 溶剂：Conditions.solvent 只有 8 个粗类别（model.SOLVENTS），
             ORD 的溶剂名要映射过去；映射不上或类别完全不符 -> 降权
          3. 没有 ORD 条件的反应类型（37 类里有 7 类无数据）-> 保守放行（1.0），
             宁可漏判也不误杀
        """
        if not self.gate_conditions or cond is None:
            return 1.0, ""
        e = self.cond_table.get(reaction_name)
        if not e:
            e = self.curated_cond_table.get(reaction_name)
        if not e:
            e = self.mined_top_cond_table.get(reaction_name)
        if not e:
            return 1.0, "无 ORD 条件数据，放行"
        reasons = []
        score = 1.0

        # ---- 温度 ----
        t = e.get("temp_C")
        if isinstance(t, dict) and t.get("min") is not None and t.get("max") is not None:
            lo, hi = float(t["min"]), float(t["max"])
            T = float(getattr(cond, "temperature", 100.0))
            if T < lo - self.gate_tol_C or T > hi + self.gate_tol_C:
                return 0.0, f"温度 {T:g}°C 超出 ORD 实测范围 [{lo:g}, {hi:g}]（容差 {self.gate_tol_C:g}）"
            if T < lo:
                score = min(score, max(0.0, 1.0 - (lo - T) / self.gate_tol_C))
                reasons.append(f"温度 {T:g}°C 低于实测下限 {lo:g}°C，降权")
            elif T > hi:
                score = min(score, max(0.0, 1.0 - (T - hi) / self.gate_tol_C))
                reasons.append(f"温度 {T:g}°C 高于实测上限 {hi:g}°C，降权")

        # ---- ★ 必需试剂（第十二轮新增：从"降权"升级到"判零"）★ ----
        #   动机（用户要的例子）：Mitsunobu 缺 DEAD 就该判零，而不是降权 0.5。
        #   数据来源：reports/aux_reagent_coverage.json（覆盖率 = 该类反应里用了它的比例）。
        #   判据：① 只有【覆盖率 >= REQUIRED_COV】的试剂才算"必需件"；
        #        ② 同功能的分子先归成一个"角色"再算覆盖率（DEAD/DIAD 都是偶氮二羧酸酯，
        #           各自覆盖率可能都不到 0.5，但加起来就是"必需"）——归并规则见 REAGENT_ROLE_SMARTS，
        #           这是【建模选择】不是实测值；
        #        ③ 条件里**没写试剂时不检查**（向后兼容：否则默认条件下这类反应全被拦死）；
        #        ④ 条件写了试剂但缺任一必需件 -> 判零（真·判据）；
        #           —— 只有 ② 归并后仍不足 0.5 时，才退回旧行为（不在 top-8 则降权 0.5）。
        aux = e.get("auxiliary_reagents") or []
        run_reagents = tuple(getattr(cond, "reagents", ()) or ())
        one = getattr(cond, "reagent", None)
        if one:
            run_reagents = run_reagents + (one,)
        if aux and run_reagents:
            units = self.required_reagent_units(reaction_name, e)
            if units:
                missing = [u for u in units
                           if not any(self._reagent_match(m, r)
                                      for m in u["members"] for r in run_reagents)]
                if missing:
                    desc = "、".join(f"{u['name']}(覆盖 {u['coverage']:.0%})"
                                     for u in missing[:3])
                    return 0.0, (f"缺该类反应的必需试剂 {desc}，判定为不发生"
                                 f"（条件里给的是 {list(run_reagents)[:3]}）")
            top = aux[:8]                     # ORD 实测最常见的 8 个辅助试剂
            # ★ 第三十四轮：这一路（降权）改成**角色级**匹配；
            #   上面的"必需试剂判零"仍是严格的字面/组件匹配（不放宽）。
            if any(self._reagent_match(a, r, allow_role=True)
                   for a in top for r in run_reagents):
                score = min(score, 1.0)       # 命中所需试剂（或同角色试剂），维持
            else:
                score = min(score, 0.5)
                reasons.append(
                    f"条件里的试剂 {list(run_reagents)[:2]} 不在该类反应的 ORD 常用试剂 "
                    f"{top[:3]} 中（同角色也不算），降权至 0.5")

        # ---- 溶剂：★ 第三十六轮重做 ★ ----
        #   旧逻辑：条件里的溶剂不在 ORD 偏好列表里 -> 降权 0.6。
        #   实测问题（第三十三/三十四轮）：`B-H` 的偏好列表 = [toluene, water, 1,4-dioxane,
        #   DMF, EtOH, EtOAc]（来自 ORD 里"用过哪些溶剂"，**不看成败**），
        #   而 HTE 里这类偶联最常用、成功率最高的 **DMSO（11,596 条 / 成功率 68.5%）根本不在表里**
        #   -> 引擎给最好的溶剂扣分，water（成功率 0.8%）反而 1.0
        #   -> 成对 AUC 0.458（**方向是反的**）。
        #   新逻辑：**有成败标签就用证据**（`reports/solvent_evidence.json`）：
        #     成功率 >= 0.5 且样本 >= 50 -> 视为适用（不加罚）
        #     成功率 <  0.5 且样本 >= 50 -> 降权（这才是"这个溶剂在这类反应里常失败"）
        #     没标签 -> 中性（**不因为"不在名单里"而扣分**；信息缺失 != 信息否定）
        sols = e.get("solvents") or []
        if sols:
            got = getattr(cond, "solvent", None)
            if got:
                sig = self._solvent_signal(reaction_name, got)
                if sig is not None:
                    if sig["verdict"] == "penalize":
                        score = min(score, 0.6)
                        reasons.append(
                            f"溶剂 {got}：该类反应在带标签数据里成功率仅 "
                            f"{sig['success_rate']:.0%}（n={sig['n']}），降权至 0.6")
                    # verdict == "ok" -> 明确适用，不加罚也不加奖（保持 score）
                elif not solvent_matches(got, sols):
                    # ① 完全没证据（名单里外的判断都无语义）-> 中性：
                    #    旧行为是降权 0.6，实测那会系统性地惩罚"没被 ORD 记录过的好溶剂"。
                    #    但保留一条**已知低覆盖**的提示，便于用户知道"没证据"。
                    reasons.append(
                        f"溶剂 {got}：无该反应类的成败标签（ORD 偏好 {sols[:3]}），"
                        f"按中性处理（不扣分）")
        return score, "；".join(reasons)

    # ---------------------------------------------------------------- 溶剂证据

    SOLVENT_EVIDENCE_PATH = _STAGE / "reports" / "solvent_evidence.json"
    _SOLV_EVID: Dict[str, Any] = {}

    @classmethod
    def _solvent_evidence(cls) -> Dict[str, Any]:
        """带成败标签的溶剂证据（`tools/build_solvent_evidence.py` 产出）。缺文件 -> 空。"""
        if not cls._SOLV_EVID:
            try:
                if cls.SOLVENT_EVIDENCE_PATH.exists():
                    import json as _json
                    with open(cls.SOLVENT_EVIDENCE_PATH, encoding="utf-8") as f:
                        cls._SOLV_EVID = _json.load(f)
                else:
                    cls._SOLV_EVID = {"classes": {}}
            except Exception:                    # noqa: BLE001 —— 静默回退到"无证据"是安全的
                cls._SOLV_EVID = {"classes": {}}
        return cls._SOLV_EVID

    def _solvent_signal(self, reaction_name: str, run_solvent: str) -> Optional[Dict[str, Any]]:
        """这个溶剂在这类反应里有带标签的成败证据吗？返回 {verdict, success_rate, n} 或 None。"""
        ev = self._solvent_evidence().get("classes", {}).get(reaction_name)
        if not ev:
            return None
        g = solvent_class(run_solvent)
        for s in ev.get("solvents", []):
            if not s.get("has_outcome") or s.get("success_rate") is None:
                continue
            if solvent_class(s.get("name")) != g:
                continue
            n = int(s.get("n") or 0)
            if n < 50:                           # 样本太少不作判据
                return None
            rate = float(s["success_rate"])
            return {"verdict": "ok" if rate >= 0.5 else "penalize",
                    "success_rate": rate, "n": n, "solvent": s.get("name")}
        return None

    @staticmethod
    def _solvent_class(name) -> str:
        """兼容旧接口：委托给 conditions/model.py 的 solvent_class()（单一真相，不再各写一份）。"""
        return solvent_class(name)

    # ---------------------------------------------------------------- 核心
    def step(self,
             compounds: Sequence[Compound],
             cond=None,
             threshold: float = 0.15,
             exclude_smiles: Optional[set] = None,
             round_no: int = 1) -> List[Product]:
        """对一批底物跑一轮两两反应。

        ★ 条件门控（2026-10-11 第十轮）★
        以前：`cond` **不参与筛选**（本 docstring 原文：SmartReact 没有条件激活模型，
              条件只标注不作判据）。
        现在：`cond` 通过 `cond_activation()` 参与筛选 ——
              每条枚举结果的反应类型拿去查 ORD 实测条件窗口（温度/溶剂），
              分数 0 的整条丢弃，0<x<1 的作为 activation 权重参与打分。
              可用 `gate_conditions=False` 关掉回退到旧行为。
        """
        exclude_smiles = exclude_smiles or set()
        subs = []
        for c in compounds:
            m = get_mol(c.smiles)
            if m is not None:
                subs.append((c, Chem.MolToSmiles(m)))
        if (len(subs) < 2 and not self.mono_templates
                and not self.curated_mono_templates
                and not self.mono_top_templates):
            return []
        if not subs:
            return []

        pairs = [(i, j) for i in range(len(subs)) for j in range(i + 1, len(subs))]
        truncated = False
        if len(pairs) > self.max_pairs:
            if self.fair_pairs:
                pairs = fair_sample_pairs(len(subs), self.max_pairs)
            else:
                pairs = pairs[:self.max_pairs]
            truncated = True

        t0 = time.time()
        n_raw = 0
        n_rev_medium = 0
        out: List[Product] = []
        seen = set()

        BATCH = 400
        # ★ 第二十二轮：单底物模板不需要"对" —— 没有对时也要跑一轮（chunk 为空，只跑单底物）
        n_batch = max(1, math.ceil(len(pairs) / BATCH))
        for b in range(n_batch):
            chunk = pairs[b * BATCH:(b + 1) * BATCH]
            payload = [(subs[i][1], subs[j][1]) for i, j in chunk]
            try:
                results = list(self._enum.enumerate_pairs(payload)) if payload else []
            except Exception:
                continue
            # ★ 第十五/十六轮：额外（ORD 自抽）模板 —— 默认【启用 K1 档】（见 __init__）★
            # ★ 第十七轮：extra_requires_accepted_pair=True 时走「非孤儿」规则（见 __init__）★
            # ★ 第二十二轮：单底物模板（mined_mono）也要在这里跑 —— 所以判据是「两者任一非空」★
            if (self.extra_templates or self.mono_templates or self.triple_templates
                    or self.curated_pair_templates or self.curated_mono_templates
                    or self.extra_top_templates or self.mono_top_templates):
                extra = self._extra_results(chunk, subs, cond)
                if self.extra_requires_accepted_pair and extra:
                    ok_pairs = set()
                    for r0 in results:
                        a0, _w0 = self.cond_activation(r0.reaction_name, cond)
                        if a0 > 0.0:
                            ok_pairs.add((r0.reactant_a, r0.reactant_b))
                    kept = [r0 for r0 in extra
                            if (r0.reactant_a, r0.reactant_b) in ok_pairs]
                    k = "自抽模板_被非孤儿规则丢弃"
                    self.gate_stats[k] = self.gate_stats.get(k, 0) + (len(extra) - len(kept))
                    extra = kept
                results = results + extra
            for r in results:
                # ★ 条件门控：这类反应在当前工艺条件下会不会发生 ★
                #   原来这里完全不看 cond，activation 写死 1.0（见下方 Product 构造）。
                #   现在：分数 0 -> 整条枚举结果丢弃；0<x<1 -> 作为 activation 参与打分。
                act, why = self.cond_activation(r.reaction_name, cond)
                if act <= 0.0:
                    key = r.reaction_name
                    self.gate_stats[key] = self.gate_stats.get(key, 0) + 1
                    continue
                comp_a = r.reactant_a
                comp_b = r.reactant_b
                # ★ D5（2026-10-13）：3 组分模板的第三个反应物（1/2 组分时为 ""）
                comp_c = getattr(r, "reactant_c", "") or ""
                # 找到来源 Compound（用于 source_*）
                src = None
                for (c, cs) in subs:
                    if cs == comp_a:
                        src = c
                        break
                if src is None:
                    src = subs[0][0]

                # ★ D2（2026-10-13）：底物的规范化 SMILES（模型要 aryl/amine 两个指纹位）
                _ca = Chem.MolToSmiles(get_mol(comp_a)) if get_mol(comp_a) else comp_a
                _cb = Chem.MolToSmiles(get_mol(comp_b)) if get_mol(comp_b) else comp_b
                _cc = (Chem.MolToSmiles(get_mol(comp_c)) if get_mol(comp_c) else comp_c) if comp_c else ""
                # ★ D5：去重后的反应物列表（单底物时 a==b，3 组分时 a/b/c）
                _distinct = []
                for _x in (_ca, _cb, _cc):
                    if _x and _x not in _distinct:
                        _distinct.append(_x)
                # ★ D1（2026-10-13，**已按 Codex 复核修正**）：反应物侧元素总量（每个反应只算一次）。
                #   坑：单底物模板构造的 `reactant_a == reactant_b == 同一个分子`，
                #   直接取两个会把底物**算两遍** -> 元素收支系统性变成"脱水形状" -> 水相一律判可疑。
                #   实测（修正前）：水杨酸单底物反应被记成 Δ=(-7,-4,-3)（应为 (0,+2,0)）。
                _react_mols = [get_mol(_x) for _x in _distinct]
                react_tot = _element_totals(_react_mols)
                _csrc = Chem.MolToSmiles(get_mol(src.smiles)) if get_mol(src.smiles) else src.smiles
                _partner = next((x for x in _distinct if x != _csrc), "")
                prods_all = list(r.products)
                n_raw += len(prods_all)
                n_take = 0
                rev_medium = self._nonpropagating(r.reaction_name, cond)
                for psm in prods_all:
                    if n_take >= self.max_products_per_pair:
                        break
                    m = get_mol(psm)
                    if m is None:
                        continue
                    cs = Chem.MolToSmiles(m)
                    if cs in exclude_smiles or cs in seen:
                        continue
                    # ★ 注意返回顺序：classify_product -> (是否保留, 是否小分子副产物)
                    try:
                        keep, is_byp = classify_product(m)
                    except Exception:
                        keep, is_byp = True, False
                    if not keep:
                        continue
                    from rdkit.Chem import Descriptors
                    pform = rdMolDescriptors.CalcMolFormula(m)
                    out.append(Product(
                        smiles=cs,
                        formula=pform,
                        element_delta=_element_delta(react_tot, pform),
                        partner_smiles=_partner,
                        mw=round(Descriptors.MolWt(m), 3),
                        heavy_atoms=m.GetNumHeavyAtoms(),
                        rule_id=r.reaction_name,
                        rule_name=r.reaction_name,
                        category=(self._rule_by_id.get(r.reaction_name, {})
                                  .get("categories", [""])[0] if
                                  self._rule_by_id.get(r.reaction_name) else ""),
                        source_smiles=Chem.MolToSmiles(get_mol(src.smiles)) if get_mol(src.smiles) else src.smiles,
                        source_name=src.name,
                        source_herb=src.herb,
                        round=round_no,
                        is_byproduct=is_byp,
                        # ★ 第十九轮：不再写死 False —— 水相里的脱水缩合类判为可逆（不传播）。
                        #   旧注释：「旧引擎的可逆性来自规则数据；SmartReact 模板无此字段，统一 False」
                        #   那等于把 cascade 的"只传播不可逆产物"闸门关掉（实测分子每轮翻倍）。
                        reversible=rev_medium,
                        activation=act,      # ★ 条件门控给出的权重（默认 1.0）
                        activation_why=(why or ("ORD 条件窗口内，无降权" if act >= 1.0
                                                else "")),
                        co_products=tuple(x for x in prods_all if x != psm),
                        # ★ D5：这条产物来自的模板 support（只打标记；0 = 不适用）
                        template_support=int((getattr(r, "product_support", None) or {}).get(psm, 0)),
                    ))
                    if rev_medium:
                        n_rev_medium += 1
                    seen.add(cs)
                    n_take += 1

        self.stats = {
            "compounds": len(subs),
            "pairs_total": len([1 for i in range(len(subs)) for j in range(i + 1, len(subs))]),
            "pairs_run": len(pairs),
            "pairs_truncated": truncated,
            "pairs_fair": bool(getattr(self, "fair_pairs", False)),
            "prefilter_checked": getattr(self, "_pf_checked", 0),
            "prefilter_skipped": getattr(self, "_pf_skipped", 0),
            "raw_products": n_raw,
            "kept": len(out),
            # ★ 第十九轮：被【介质相关可逆性】标为可逆的产物数（它们不参与级联传播）
            "reversible_by_medium": n_rev_medium,
            "seconds": round(time.time() - t0, 2),
            "round": round_no,
            # ★ 条件门控统计：哪些反应类型被当前条件判零、各拦了多少条
            "gated_zero_total": sum(self.gate_stats.values()),
            "gated_zero_by_type": dict(sorted(self.gate_stats.items(),
                                              key=lambda x: -x[1])[:10]),
        }
        if self.verbose:
            print(f"   [step r{round_no}] 底物 {len(subs)} 对 {len(pairs)} "
                  f"原始产物 {n_raw} 保留 {len(out)} ({self.stats['seconds']}s)")
        return out


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    from cascade import cascade
    from model import Conditions          # 旧架构是扁平导入（conditions/ 在 sys.path 上）

    print("=" * 92)
    print("SmartReactEngine 自检")
    print("=" * 92)

    t0 = time.time()
    eng = SmartReactEngine(max_products_per_pair=6, max_pairs=3000, verbose=True)
    print(f"引擎构造 {time.time()-t0:.1f}s（含加载 9770 条模板）")
    print(f"规则粒度 = 反应类型，共 {len(eng.rules)} 条")
    top = sorted(eng.rules, key=lambda r: -r["priority"])[:5]
    print("priority 最高的 5 类（由 ORD 证据次数数据驱动）：")
    for r in top:
        print(f"   {r['priority']:.3f}  {r['name']:<30} ORD证据 {r['ord_evidence']}")

    # 用一组【有反应把手的中等分子】做级联自检
    # （产物必须大于 BYPRODUCT_MAX_MW=46 才能成为下一轮底物，否则被判副产物不传播）
    seeds = [Compound(smiles=s, name=n, herb="selftest") for s, n in [
        ("O=C(O)c1ccccc1O",              "水杨酸"),
        ("NCCc1ccc(O)cc1",               "酪胺"),
        ("OCC(O)CO",                     "甘油"),
        ("c1ccc(B(O)O)cc1",              "苯硼酸"),
        ("CC(=O)c1ccc(O)cc1",            "对羟基苯乙酮"),
    ]]
    cond = Conditions(solvent="water", temperature=100.0, time_min=60.0)

    print()
    print("跑级联：max_rounds=3, min_new=3, frontier_limit=12")
    print("（验证两件事：① 多步 ② 三组分——A+B 成中间体，中间体再和 C 反应）")
    t0 = time.time()
    res = cascade(eng, seeds, cond, max_rounds=3, min_new=3, frontier_limit=12)
    print(f"级联耗时 {time.time()-t0:.1f}s")
    print(f"   跑了 {res.rounds} 轮，产物合计 {res.total}")
    for st in res.round_stats:
        print(f"   第 {st['round']} 轮：新 {st['new']}，"
              f"可传播 {st['irreversible_new']}，低于门槛 {st['below_floor']}")

    print()
    prods = res.products
    if isinstance(prods, dict):
        prods = list(prods.values())
    prods = sorted(prods, key=lambda p: -p.score)[:14]
    print("产物样例（按分数，标注轮次——r2/r3 就是多步的产物）：")
    for p in prods:
        tag = "副产物" if p.is_byproduct else "主体"
        print(f"   {p.score:.3f} r{p.round} [{tag}] {p.rule_name:<26} {p.smiles[:50]}")
