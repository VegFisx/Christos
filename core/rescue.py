# -*- coding: utf-8 -*-
"""抢救层：用低支持度模板补主池漏掉的产物（默认关闭）。

背景（第一百五十六轮）：
  11,999 条反应里 896 条（7.47%）完全生成不出目标产物；归因显示
  0% 是过滤问题、3% 是上限截断、26% 是模板没装载、**71% 是真缺口**。
  低支持度（support 1-4）的 24.6 万条模板能救回 50% 的缺失，
  其中 62% 是真泛化（来源是另一条反应），12% 是同一反应（泄漏）。

本模块只做「候选生成」：用底物原子环境做必要条件的索引筛选，再跑真实反应。
不读产物、不用标签，生产可用。

特征 = (元素, 总氢数, 度数, 芳香性)，打包成一个小整数；模板未指定的 H/度数
进「通配元组」，只按 (元素, 芳香性) 计数。这样 24.6 万条模板的索引只占
几十 MB（旧版 Counter 方案每 worker 约 2.2 GB，2 个 worker 就触发 6 GB 护栏）。

用法（引擎侧）：
  SmartReactEngine(..., rescue=True, rescue_min_candidates=10)
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "reports" / "mined_forward_templates_full.jsonl"
# ★ 第 163 轮：产品默认覆盖池 = USPTO 训练半区挖的通用正向模板（反应级排除官方 test）。
#   11,453 条 support≥1；官方全量召回 92.19→94.99%，top-1 73.72→73.70，候选 +1.6/反应。
#   与 FULL（ORD 低支持度池，support 1-4）不同：train 池质量高、预筛后候选极少。
TRAIN_COVERAGE = ROOT / "reports" / "mined_forward_templates_uspto_train.jsonl"

_NUM2SYM = {6: "C", 7: "N", 8: "O", 9: "F", 15: "P", 16: "S", 17: "Cl",
            35: "Br", 53: "I", 5: "B", 14: "Si", 34: "Se"}
# 两字母元素白名单：否则 [CH2:10] / [NH2;D1] 会被当成 "Ch" / "Nh"
_TWO = ("Cl", "Br", "Si", "Se", "Na", "Li", "Mg", "Ca", "Fe", "Cu", "Zn",
        "Pd", "Ni", "Pt", "Al", "Sn", "Mn", "Co", "Cr", "Mo", "Ag", "Au",
        "Hg", "Pb", "As", "Sb", "Bi", "Te", "Ti", "Zr")
_SYMS = ["C", "N", "O", "S", "P", "F", "Cl", "Br", "I", "B", "Si", "Se",
         "Na", "Li", "Mg", "Ca", "Fe", "Cu", "Zn", "Pd", "Ni", "Pt", "Al",
         "Sn", "Mn", "Co", "Cr", "Mo", "Ag", "Au", "Hg", "Pb", "As", "Sb",
         "Bi", "Te", "Ti", "Zr", "*"]
_EID = {s: i for i, s in enumerate(_SYMS)}

_BRACKET = re.compile(r"\[([^\]]+)\]")
_BARE = re.compile(r"Cl|Br|[BCNOPSFIcnops]")


def _pack(eid: int, h: int, d: int, ar: int) -> int:
    return (((eid * 11) + (h + 1)) * 11 + (d + 1)) * 2 + ar


def _atom(tok: str):
    """SMARTS 原子 token -> (eid, H, 度数, 芳香) 或 None。未指定记 -1。"""
    elem = None
    m = re.match(r"#(\d+)", tok)
    if m:
        elem = _NUM2SYM.get(int(m.group(1)))
    else:
        for s in _TWO:
            if tok.startswith(s):
                elem = s
                break
        if elem is None:
            m = re.match(r"[A-Za-z]", tok)
            if m:
                elem = m.group(0)
    if not elem:
        return None
    arom = 1 if elem[0].islower() else 0
    elem = elem[0].upper() + elem[1:].lower()
    if elem not in _EID:
        return None
    mh = re.search(r"H(\d*)", tok)
    hv = int(mh.group(1) or 1) if mh else -1
    md = re.search(r"D(\d)", tok)
    dv = int(md.group(1)) if md else -1
    return (_EID[elem], min(max(hv, -1), 9), min(max(dv, -1), 9), arom)


def _side(smarts: str):
    """返回 (exact_sorted_tuple, wild_sorted_tuple)。"""
    ex, wl = [], []
    for tok in _BRACKET.findall(smarts):
        a = _atom(tok)
        if not a:
            continue
        e, h, d, ar = a
        if h < 0 or d < 0:
            wl.append((e, ar))
        else:
            ex.append(_pack(e, h, d, ar))
    bare = _BRACKET.sub(" ", smarts)
    for tok in _BARE.findall(bare):
        e = _EID.get(tok[0].upper() + tok[1:].lower())
        if e is None:
            continue
        wl.append((e, 1 if tok[0].islower() else 0))
    return tuple(sorted(ex)), tuple(sorted(wl))


def _mol_counts(m):
    ex = Counter()
    ea = Counter()
    for a in m.GetAtoms():
        e = _EID.get(a.GetSymbol())
        if e is None:
            continue
        ar = 1 if a.GetIsAromatic() else 0
        ex[_pack(e, min(a.GetTotalNumHs(), 9), min(a.GetDegree(), 9), ar)] += 1
        ea[(e, ar)] += 1
    return ex, ea


def _runs(t):
    i = 0
    n = len(t)
    while i < n:
        v = t[i]
        j = i + 1
        while j < n and t[j] == v:
            j += 1
        yield v, j - i
        i = j


def _viable(ex, wl, sub_ex, sub_ea) -> bool:
    for v, n in _runs(ex):
        if sub_ex.get(v, 0) < n:
            return False
    for v, n in _runs(wl):
        if sub_ea.get(v, 0) < n:
            return False
    return True


class RescuePool:
    """低支持度模板池；构建一次，查询多次。"""

    def __init__(self, path: Path = FULL, min_support: int = 1,
                 max_support: int = 4, verbose: bool = True):
        self.tpls = []
        t0 = time.time()
        n_bad = 0
        for line in open(path, encoding="utf-8"):
            d = json.loads(line)
            s = int(d.get("support") or 0)
            if not (min_support <= s <= max_support):
                continue
            t = d.get("template") or ""
            if ">>" not in t:
                n_bad += 1
                continue
            ex, wl = _side(t.split(">>", 1)[0])
            if not ex and not wl:
                n_bad += 1
                continue
            self.tpls.append((t, s, ex, wl))
        self.n_bad = n_bad
        if verbose:
            print("[rescue] 索引 %d 条模板（support %d-%d，坏 %d），%.0f s"
                  % (len(self.tpls), min_support, max_support, n_bad,
                     time.time() - t0), file=sys.stderr)

    def run(self, mols):
        """返回 [(产物 SMILES, 模板, support)]（未去重、未过滤）。"""
        from rdkit import Chem
        from rdkit.Chem import AllChem

        if not mols:
            return []
        sub_ex, sub_ea = Counter(), Counter()
        for m in mols:
            a, b = _mol_counts(m)
            sub_ex += a
            sub_ea += b
        cand = [(t, s) for t, s, ex, wl in self.tpls
                if _viable(ex, wl, sub_ex, sub_ea)]
        out = []
        for t, s in cand:
            try:
                rxn = AllChem.ReactionFromSmarts(t)
            except Exception:
                continue
            args = tuple(mols)
            for order in ([args] if len(mols) == 1 else [args, tuple(reversed(args))]):
                try:
                    outs = rxn.RunReactants(order)
                except Exception:
                    continue
                for prod in outs:
                    for pm in prod:
                        try:
                            Chem.SanitizeMol(pm)
                            out.append((Chem.MolToSmiles(pm), t, s))
                        except Exception:
                            continue
        return out
