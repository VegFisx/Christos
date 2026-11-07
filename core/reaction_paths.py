# -*- coding: utf-8 -*-
"""反应路径：把产物台账里的「一跳行」还原成「起始成分 → … → 产物」的链。

为什么要有这个模块
------------------
台账 CSV 每行只记录**一跳**：`source_smiles --[rule]--> product_smiles`。
多轮枚举时，上一轮的产物会变成下一轮的底物，于是「甘草苷 → 苷元 → 脱水产物」
这种**过程化学**的路径散落在多行里，靠眼睛看不出来。

这里把行拼成图（product -> 产生它的那些跳），再从目标产物往回走，
走到底（某个分子没有产生它的行 = 它是输入成分/种子）就是一条完整路径。
**只读台账，不改、不排序、不新增化学假设。**

口径（写清楚，免得以后各说各话）
------------------------------
- 一跳 = 台账一行 = 一个规则作用在一对底物上。
- 一条链 = 从种子到目标的若干跳；同一个产物可能有多条链（不同规则/不同来源）。
- 路径不是生化合成路线：它只表达「在这个条件下，按这些规则，A 能变成 B」。
- 环状/自催化会出现重复分子，`visited` 防死循环；深度上限默认 12 跳。
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

__all__ = [
    "Hop",
    "load_hops",
    "hops_from_paths",
    "expand_co_products",
    "load_rule_names",
    "build_index",
    "chains",
    "render_chain",
    "render_chains",
    "chains_for_run",
    "formula_of",
    "looks_like_smiles",
    "heavy_atoms",
    "atom_keep",
    "atom_conservation",
]

MAX_DEPTH = 12
MAX_CHAINS = 8


@dataclass
class Hop:
    """台账里的一跳：source --[rule]--> product。"""

    product: str
    source: str
    rule: str = ""
    round: str = ""
    product_formula: str = ""
    product_mw: str = ""
    source_name: str = ""
    source_herb: str = ""
    activation: str = ""
    activation_why: str = ""
    direction_cn: str = ""
    extent: str = ""
    extent_band: str = ""
    co_products: str = ""
    reversible: str = ""
    co: bool = False          # True = 这一跳的产物是伴生产物（来自 co_products，不是主产物）
    alt_rules: str = ""       # 同一结构还能由哪些规则给出（结构去重时后到的那几条）

    @property
    def label(self) -> str:
        """这一跳的产物叫什么：优先分子式（不含立体信息、最稳），否则 SMILES 前缀。"""
        if self.product_formula:
            return self.product_formula
        return (self.product or "?")[:32]


def _s(x) -> str:
    return "" if x is None else str(x).strip()


def looks_like_smiles(s: str) -> bool:
    """判断一个「名字」其实是 SMILES（把 --smiles 输入的名字字段当成了名字的老问题）。"""
    s = (s or "").strip()
    if not s:
        return False
    if len(s) > 40:
        return True
    if any(ch in s for ch in "=#[]@\\/"):
        return True
    return s.count("(") >= 2


def formula_of(smiles: str) -> str:
    """分子式（有 RDKit 才算；没有就返回空串，调用方退回 SMILES 前缀）。

    为什么路径里要算这个：中间体没有名字，SMILES 前缀读不了；
    分子式一眼能看出水解掉了几个糖。
    """
    try:
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        m = Chem.MolFromSmiles(smiles or "")
        if m is None:
            return ""
        return CalcMolFormula(m)
    except Exception:
        return ""


def heavy_atoms(smiles: str) -> int:
    """重原子数（RDKit 不可用或解析失败返回 0）。"""
    try:
        from rdkit import Chem
        m = Chem.MolFromSmiles(smiles or "")
        return 0 if m is None else int(m.GetNumHeavyAtoms())
    except Exception:
        return 0


def atom_keep(source_smiles: str, product_smiles: str) -> Optional[float]:
    """一跳的原子保留率 = 产物重原子数 / 底物重原子数。

    为什么需要（第八十九轮实测）：ORD mined 模板只记主产物，有的模板会把底物
    大半删掉（``C36H38O16`` → ``C10H12O3``，26 个碳、13 个氧凭空消失），
    台账上却和正常反应长得一样。比率远小于 1 就是这类模板的指纹。
    判据是**观测量**，不是化学断言：缩合/加成会让产物变大（>1），也属正常。
    """
    s = heavy_atoms(source_smiles)
    p = heavy_atoms(product_smiles)
    if s <= 0 or p <= 0:
        return None
    return p / s


def atom_conservation(source_smiles: str, product_smiles: str, co_products="",
                      partner_smiles: str = "") -> Optional[float]:
    """一层反应之后的原子守恒率 = (主产物 + 伴生产物) 重原子数 / 先验总重原子数。

    为什么不用单看主产物：水解是「一分为二」，主产物往往只是一半（糖，或苷元），
    单看主产物会让每条水解都像在删原子。把 ``co_products``（``|`` 分隔）加上，
    才反映「这一步到底留没留下底物里的原子」。

    双底物（``partner_smiles`` 非空）时分母要加上第二个底物，否则缩合/成键类反应
    （产物原子数 > 单底物）会被误判；第 90 轮的 ``condensation_aldol_001`` 假阳性
    就是这个口径缺了分母（第 119 轮修）。

    * ``≈ 1`` 正常（拆分、分子内重排）。
    * ``< 0.7`` 疑似模板删原子（mined 模板只记主产物时的典型指纹）。
    * ``> 1`` 正常（加成、缩合、两底物成键）。
    """
    s = heavy_atoms(source_smiles)
    if s <= 0:
        return None
    if str(partner_smiles or "").strip():
        s += heavy_atoms(partner_smiles)
        if s <= 0:
            return None
    total = heavy_atoms(product_smiles)
    for frag in str(co_products or "").split("|"):
        frag = frag.strip()
        if frag:
            total += heavy_atoms(frag)
    if total <= 0:
        return None
    return total / s


def hops_from_paths(paths: Iterable[dict]) -> List[Hop]:
    """把内存里的 ``inv.paths``（PATH_FIELDS 字典列表）直接转成 Hop。

    用途：不用落盘 CSV 也能做路径分析（文献对照、单元测试）。
    键名与 ``PATH_FIELDS`` 一致，缺键按空串处理。
    """
    out: List[Hop] = []
    for r in paths or ():
        product = _s(r.get("product_smiles"))
        source = _s(r.get("source_smiles"))
        if not product or not source:
            continue
        out.append(Hop(
            product=product,
            source=source,
            rule=_s(r.get("rule_name")),
            alt_rules=_s(r.get("also_rules")),
            round=_s(r.get("round")),
            product_formula=_s(r.get("formula")),
            product_mw=_s(r.get("mw")),
            source_name=_s(r.get("source_name")),
            source_herb=_s(r.get("source_herb")),
            activation=_s(r.get("activation")),
            activation_why=_s(r.get("activation_why")),
            direction_cn=_s(r.get("direction_cn")),
            extent=_s(r.get("extent")),
            extent_band=_s(r.get("extent_band")),
            co_products=_s(r.get("co_products")),
            reversible=_s(r.get("reversible")),
        ))
    return out


def expand_co_products(hops: Iterable[Hop], *, drop_smiles=()) -> List[Hop]:
    """把每一跳的伴生产物（``co_products``，用 ``|`` 分隔）也变成一跳。

    为什么需要：双底物规则（水解、酯化…）里引擎通常把「大的那一半」当主产物、
    另一半塞进 ``co_products``。只看主产物会漏掉整条链的一半分子 ——
    例：乌头碱的酯水解，脱酯骨架（苯甲酰乌头原碱，C32H45NO10）就在 co_products 里，
    只看主产物会误判成「文献产物只能靠酯的氨解得到」。

    返回的伴生跳带 ``co=True``，渲染时会标「伴生产物」。
    """
    _fcache: Dict[str, str] = {}
    out: List[Hop] = []
    seen = set()
    drop = set(drop_smiles or ())
    for h in hops:
        out.append(h)
        seen.add((h.product, h.source, h.rule, h.round))
        for frag in (h.co_products or "").split("|"):
            frag = frag.strip()
            if not frag or frag in drop:
                continue
            key = (frag, h.source, h.rule, h.round)
            if key in seen:
                continue
            seen.add(key)
            if frag not in _fcache:
                _fcache[frag] = formula_of(frag)
            out.append(Hop(
                product=frag, source=h.source, rule=h.rule, round=h.round,
                product_formula=_fcache[frag], source_name=h.source_name,
                source_herb=h.source_herb, activation=h.activation,
                activation_why=h.activation_why, direction_cn=h.direction_cn,
                extent=h.extent, extent_band=h.extent_band,
                co_products=h.co_products, reversible=h.reversible, co=True,
            ))
    return out


def load_hops(csv_path) -> List[Hop]:
    """从台账 CSV 读跳。字段缺失时按空串处理（旧台账也能读）。"""
    p = Path(csv_path)
    out: List[Hop] = []
    with p.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            product = _s(r.get("product_smiles"))
            source = _s(r.get("source_smiles"))
            if not product or not source:
                continue
            out.append(Hop(
                product=product,
                source=source,
                rule=_s(r.get("rule_name")),
                alt_rules=_s(r.get("also_rules")),
                round=_s(r.get("round")),
                product_formula=_s(r.get("formula")),
                product_mw=_s(r.get("mw")),
                source_name=_s(r.get("source_name")),
                source_herb=_s(r.get("source_herb")),
                activation=_s(r.get("activation")),
                activation_why=_s(r.get("activation_why")),
                direction_cn=_s(r.get("direction_cn")),
                extent=_s(r.get("extent")),
                extent_band=_s(r.get("extent_band")),
                co_products=_s(r.get("co_products")),
                reversible=_s(r.get("reversible")),
            ))
    return out


def load_rule_names(path=None) -> Dict[str, str]:
    """规则 id -> 中文名（rules/rules.json）。找不到就返回空表，调用方退回 id。"""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "rules" / "rules.json"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    names = {}
    for r in (data.get("rules") or []):
        rid = _s(r.get("id"))
        if rid:
            names[rid] = _s(r.get("name")) or rid
    return names


def build_index(hops: Iterable[Hop]) -> Dict[str, List[Hop]]:
    """product SMILES -> 产生它的跳列表（只保留允许继续往回走的方向）。"""
    idx: Dict[str, List[Hop]] = defaultdict(list)
    for h in hops:
        idx[h.product].append(h)
    return dict(idx)


def _num_round(x: str) -> int:
    try:
        return int(float(x))
    except Exception:
        return 0


def chains(target: str,
           index: Dict[str, List[Hop]],
           *,
           seeds: Optional[Sequence[str]] = None,
           max_chains: int = MAX_CHAINS,
           max_depth: int = MAX_DEPTH,
           prefer: str = "round") -> List[List[Hop]]:
    """从目标产物往回走，返回若干条完整链（每条链 = 从种子到目标的跳，顺序为时间正序）。

    seeds: 已知输入成分的 SMILES 集合。给了就用它判定"走到头了"；
           不给就按"这个分子没有任何产生它的跳"判定为起点。
    prefer: "round" 优先浅的（轮次少的路径），"activation" 优先条件分高的。
    """
    seed_set = set(seeds or ())
    found: List[List[Hop]] = []
    stack: List[Hop] = []
    seen_paths = set()

    def score(h: Hop):
        if prefer == "activation":
            try:
                return -float(h.activation)
            except Exception:
                return 0.0
        return _num_round(h.round)

    def walk(smi: str, depth: int, visited: set) -> None:
        if len(found) >= max_chains:
            return
        incoming = index.get(smi) or []
        at_seed = bool(seed_set) and smi in seed_set
        if not incoming or at_seed:
            # 走到头：这是一个种子（输入成分），或者台账里没有它的上游（被截断/未保留）
            chain = list(reversed(stack))
            key = tuple((h.source, h.rule, h.product) for h in chain)
            if chain and key not in seen_paths:
                seen_paths.add(key)
                found.append(chain)
            return
        if depth >= max_depth:
            return
        for h in sorted(incoming, key=score):
            if h.source in visited:
                continue          # 防环；环本身不在这里展开
            stack.append(h)
            visited.add(h.product)
            walk(h.source, depth + 1, visited)
            visited.discard(h.product)
            stack.pop()
            if len(found) >= max_chains:
                return

    walk(target, 0, {target})
    return found


def _hop_text(h: Hop, rule_names: Optional[Dict[str, str]] = None,
              lang: str = "zh") -> str:
    name = (rule_names or {}).get(h.rule) or h.rule or "?"
    bits = [name]
    if h.round:
        bits.append(("第 %s 轮" % h.round) if lang == "zh" else ("round %s" % h.round))
    if h.activation:
        bits.append(("条件 %s" % h.activation) if lang == "zh" else ("activation %s" % h.activation))
    if h.extent_band:
        band = {"major": "主要", "minor": "次要", "none": "痕量"}.get(h.extent_band, h.extent_band)
        txt = ("进程 %s" % band) if lang == "zh" else ("extent %s" % h.extent_band)
        if h.extent:
            txt += " (%s)" % h.extent
        bits.append(txt)
    if h.direction_cn:
        bits.append(str(h.direction_cn))
    if h.co:
        bits.append("伴生产物" if lang == "zh" else "co-product")
    return " · ".join(bits)


def _end_label(smi: str, hops: Sequence[Hop], labels: Optional[Dict[str, str]] = None) -> str:
    """分子怎么称呼：调用方给的标签 > 台账里的来源名 > 分子式 > SMILES 前缀。"""
    if labels and labels.get(smi):
        return labels[smi]
    for h in hops:
        if h.source == smi and h.source_name:
            return h.source_name
    for h in hops:
        if h.product == smi and h.product_formula:
            return h.product_formula
    return smi[:32]


def render_chain(chain: Sequence[Hop], rule_names: Optional[Dict[str, str]] = None,
                 labels: Optional[Dict[str, str]] = None,
                 lang: str = "zh") -> str:
    """把一条链渲染成一行文字：`甘草苷 --[糖苷水解 · 第1轮]--> C30H50O2 --[...]--> C30H48O`。"""
    if not chain:
        return ""
    arrow = " --[%s]--> "
    parts = [_end_label(chain[0].source, chain, labels)]
    for h in chain:
        parts.append(arrow % _hop_text(h, rule_names, lang))
        parts.append(_end_label(h.product, chain, labels))
    return "".join(parts)


def render_chains(chains_list: Sequence[Sequence[Hop]],
                  rule_names: Optional[Dict[str, str]] = None,
                  labels: Optional[Dict[str, str]] = None,
                  lang: str = "zh") -> List[str]:
    return [render_chain(c, rule_names, labels, lang) for c in chains_list]


def chains_for_run(out_dir, target: str = "", *, rule_names=None,
                   labels=None, max_chains: int = MAX_CHAINS) -> List[str]:
    """便捷入口：给一个 predict 输出目录，列出某个产物（或全部多步产物）的路径文字。

    只读：自动找目录里最新的 *.csv（台账）。target 为空时返回所有「≥2 跳」产物的路径。
    """
    d = Path(out_dir)
    csvs = sorted(d.glob("*.csv"))
    if not csvs:
        return []
    hops = load_hops(csvs[-1])
    index = build_index(hops)
    names = rule_names if rule_names is not None else load_rule_names()
    if target:
        return render_chains(chains(target, index, max_chains=max_chains), names, labels)
    out = []
    for smi, hs in index.items():
        if max(_num_round(h.round) for h in hs) >= 2:
            for line in render_chains(chains(smi, index, max_chains=max_chains), names, labels):
                out.append(line)
    return out
