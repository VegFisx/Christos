# -*- coding: utf-8 -*-
r"""ORD 自抽正向模板的【加载 + 套用】库（单一真相，别再各写一份）。

模板文件由 tools/forward_template_mining.py 产出：
  reports/mined_forward_templates.jsonl
  每行: {"template": SMARTS(正向 底物>>产物), "generalized": SMARTS 或 null, "support": int}

口径（写死）：
  support = 该模板在【train】漏项里复现出的反应条数（见 forward_template_mining.py）
  套用时按 support 降序取前 limit 个 —— 与挖掘脚本的选择顺序一致（可复现）
  应用产物一律 sanitize + 去映射 canonical（isomericSmiles=False）

被谁用：
  · core/smartreact_engine.py（可选开关 extra_templates_path）
  · tools/hte_fpr_after_integration.py（HTE 假阳性复测）
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions

RDLogger.DisableLog("rdApp.*")

DEFAULT_PATH = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports") / \
    "mined_forward_templates.jsonl"


@dataclass(frozen=True)
class MinedTemplate:
    smarts: str
    support: int


def load_mined_templates(path: Optional[Path] = None,
                         min_support: int = 1,
                         generalized: bool = False,
                         limit: Optional[int] = None) -> List[MinedTemplate]:
    """读模板文件，按 support 降序返回前 limit 个（支持数 >= min_support）。"""
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        raise FileNotFoundError(f"模板文件不存在: {p}（先跑 tools/forward_template_mining.py）")
    out: List[MinedTemplate] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        # ★ 2026-10-13：兼容两种键名（既有文件用 `template`；D5 的 3 组分库用 `smarts`）
        sm = d.get("generalized") if generalized else (d.get("template") or d.get("smarts"))
        if not sm:
            continue
        sup = int(d.get("support", 0))
        if sup < min_support:
            continue
        out.append(MinedTemplate(smarts=sm, support=sup))
    out.sort(key=lambda t: (-t.support, t.smarts))
    if limit is not None:
        out = out[:limit]
    return out


def compile_templates(templates: Sequence[MinedTemplate]
                      ) -> Tuple[List[Tuple[str, object]], int]:
    """编译成 RDKit 反应对象。返回 ([(smarts, rx)], 编译失败数)。

    只保留【恰好 2 个反应物模板】的（我们只按两两底物套用）。
    """
    compiled, n_fail = [], 0
    for t in templates:
        try:
            rx = rdChemReactions.ReactionFromSmarts(t.smarts)
        except Exception:
            n_fail += 1
            continue
        if rx is None or rx.GetNumReactantTemplates() != 2:
            n_fail += 1
            continue
        compiled.append((t.smarts, rx))
    return compiled, n_fail


def _canon(mol) -> Optional[str]:
    try:
        Chem.SanitizeMol(mol)
        for a in mol.GetAtoms():
            a.SetAtomMapNum(0)
        return Chem.MolToSmiles(mol, isomericSmiles=False)
    except Exception:
        return None


def compile_templates_all(templates: Sequence[MinedTemplate]
                          ) -> Tuple[Dict[int, List[Tuple[str, object]]], int]:
    """按【反应物个数】分组编译。返回 ({arity: [(smarts, rx)]}, 编译失败数)。

    ★ 为什么需要它（第二十二轮实测）：`compile_templates()` 只收「恰好 2 个反应物」，
    而 ORD 里 **21.9% 是单底物反应**（水解/氧化/还原/脱羧/消除），自抽的 3,256 条单底物模板
    正在被整类丢弃。这里保留全部元数，由调用方决定用哪些。
    """
    by_arity: Dict[int, List[Tuple[str, object]]] = {}
    n_fail = 0
    for t in templates:
        try:
            rx = rdChemReactions.ReactionFromSmarts(t.smarts)
        except Exception:
            n_fail += 1
            continue
        if rx is None or rx.GetNumReactantTemplates() < 1:
            n_fail += 1
            continue
        by_arity.setdefault(rx.GetNumReactantTemplates(), []).append((t.smarts, rx))
    return by_arity, n_fail


def needs_co_reagent(smarts: str) -> Optional[bool]:
    """模板的产物侧有没有【未映射的重原子】？有 -> 这个原子是试剂带进来的。

    ★ 用途（第二十二轮）：单底物模板里有一大批是"底物 + 试剂"型
    （如 `[C](=O)[OH] >> C-[O]-[C](=O)` 的甲酯化，那个 `C-` 来自甲醇）。
    直接套用等于**假设试剂一定在场**，会凭空造出甲酯/乙酯/N-Boc。
    → 只把**产物侧全是映射原子**（= 自给自足：异构化/消除/脱羧/开环）的模板默认启用；
      需要共试剂的留给"条件层"（试剂在不在）去门控。
    """
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        return None
    if rx is None or rx.GetNumProductTemplates() != 1:
        return None
    patt = rx.GetProductTemplate(0)
    for a in patt.GetAtoms():
        if a.GetAtomicNum() > 1 and a.GetAtomMapNum() == 0:
            return True
    return False


_H_SPEC = re.compile(r"H(\d*)(?=[;&\]:])")


def _h_of_smarts_atom(atom_smarts: str) -> Optional[int]:
    """从原子的 SMARTS 片段里读氢数：`[CH2;D2;+0:2]`->2、`[OH;D1;+0:3]`->1、`[O;H0;D1;+0:3]`->0。

    ★ 为什么不用 RDKit 的价态接口（2026-10-12 实测）：SMARTS **查询原子**上
    `GetTotalNumHs()` 直接抛 `Pre-condition Violation: calcImplicitValence() 未调用`；
    `GetExplicitValence()` 同样抛异常。所以只能从 SMARTS 文本读。
    无 H 指定符（如 `[C:1]`）-> 返回 None（= 未指定，不参与净氢计算）。
    """
    m = _H_SPEC.search(atom_smarts or "")
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else 1


def delta_h(smarts: str) -> Optional[int]:
    """模板反应中心上的**净氢变化**：按映射号配对，Σ(产物 H − 反应物 H)。

    只统计**两侧都出现、且都显式写了 H 指定符**的映射原子（其余跳过）。
    ΔH>0 -> 加氢（需还原剂）；ΔH<0 -> 脱氢/氧化（需氧化剂）；None -> 判不了。
    """
    try:
        rx = rdChemReactions.ReactionFromSmarts(smarts)
    except Exception:
        return None
    if rx is None:
        return None

    def hmap(patts) -> Dict[int, Optional[int]]:
        d: Dict[int, Optional[int]] = {}
        for p in patts:
            for a in p.GetAtoms():
                if a.GetAtomicNum() <= 1:
                    continue
                mp = a.GetAtomMapNum()
                if mp:
                    d[mp] = _h_of_smarts_atom(a.GetSmarts())
        return d

    try:
        R, P = hmap(rx.GetReactants()), hmap(rx.GetProducts())
    except Exception:
        return None
    delta, seen = 0, False
    for mp in set(R) & set(P):
        hr, hp = R[mp], P[mp]
        if hr is None or hp is None:
            continue
        delta += hp - hr
        seen = True
    return delta if seen else None


def redox_hint(smarts: str) -> Optional[str]:
    """这个模板隐含什么氧化还原环境？返回 'reduce' / 'oxidize' / None（不需要）。"""
    d = delta_h(smarts)
    if d is None:
        return None
    if d > 0:
        return "reduce"
    if d < 0:
        return "oxidize"
    return None


def compile_templates_report(templates: Sequence[MinedTemplate]
                          ) -> Tuple[List[Tuple[str, object]], int, int, Dict[int, int]]:
    """★ D5（2026-10-13）：编译并**分开报告**两种丢弃原因。

    为什么要有它（AGENTS.md 六-4：不许把不同原因并成一个计数）：
    旧的 `compile_templates()` 把「编译失败」和「元数≠2」都算进同一个 `n_fail`，
    于是实测 362 条 arity=3~4 的自抽模板被**静默丢弃**，报告里却显示成「编译失败」。

    返回 `(compiled_arity2, n_compile_fail, n_arity_dropped, arity_hist)`。
    """
    hist: Dict[int, int] = {}
    compiled: List[Tuple[str, object]] = []
    n_fail = 0
    n_arity = 0
    for t in templates:
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
        if a != 2:
            n_arity += 1
            continue
        compiled.append((t.smarts, rx))
    return compiled, n_fail, n_arity, hist


def apply_triple_support(compiled_with_support, mol_a, mol_b, mol_c) -> Dict[str, int]:
    """★ D5：三元组套模板，返回 `{产物 canonical SMILES: 命中模板的 support 最大值}`。

    为什么要有它：`apply_triple` 只回产物集合，**丢掉了"这条产物来自哪条模板/那条模板见过几次"**，
    而用户要的是"给只见过一次的套路打标记"（不删产物）。
    """
    got: Dict[str, int] = {}
    if mol_a is None or mol_b is None or mol_c is None:
        return got
    for _sm, rx, sup in compiled_with_support:
        try:
            outs = rx.RunReactants((mol_a, mol_b, mol_c))
        except Exception:
            continue
        for tup in outs:
            for pmol in tup:
                cs = _canon(pmol)
                if cs and int(sup) > got.get(cs, 0):
                    got[cs] = int(sup)
    return got


def apply_triple(compiled: Sequence[Tuple[str, object]],
                 mol_a, mol_b, mol_c) -> Set[str]:
    """★ D5：把【3 个反应物】的模板套到三个分子上（口径与 apply_pair 一致）。"""
    got: Set[str] = set()
    if mol_a is None or mol_b is None or mol_c is None:
        return got
    for _sm, rx in compiled:
        try:
            outs = rx.RunReactants((mol_a, mol_b, mol_c))
        except Exception:
            continue
        for tup in outs:
            for pmol in tup:
                cs = _canon(pmol)
                if cs:
                    got.add(cs)
    return got


def apply_single(compiled: Sequence[Tuple[str, object]], mol) -> Set[str]:
    """把【1 个反应物】的模板套到单个分子上。"""
    got: Set[str] = set()
    if mol is None:
        return got
    for _sm, rx in compiled:
        try:
            outs = rx.RunReactants((mol,))
        except Exception:
            continue
        for tup in outs:
            for pmol in tup:
                cs = _canon(pmol)
                if cs:
                    got.add(cs)
    return got


def apply_pair(compiled: Sequence[Tuple[str, object]],
               mol_a, mol_b) -> Set[str]:
    """把模板库套到一对分子上，返回产物 canonical SMILES 集合。"""
    got: Set[str] = set()
    if mol_a is None or mol_b is None:
        return got
    for _sm, rx in compiled:
        try:
            outs = rx.RunReactants((mol_a, mol_b))
        except Exception:
            continue
        for tup in outs:
            for pmol in tup:
                cs = _canon(pmol)
                if cs:
                    got.add(cs)
    return got


def apply_pair_smiles(compiled: Sequence[Tuple[str, object]],
                      smi_a: str, smi_b: str) -> Set[str]:
    """同 apply_pair，但输入是 SMILES。"""
    return apply_pair(compiled, Chem.MolFromSmiles(smi_a), Chem.MolFromSmiles(smi_b))


__all__ = ["MinedTemplate", "load_mined_templates", "compile_templates",
           "compile_templates_all", "compile_templates_report",
           "needs_co_reagent", "delta_h", "redox_hint",
           "apply_single", "apply_pair", "apply_pair_smiles", "apply_triple",
           "apply_triple_support", "DEFAULT_PATH"]
