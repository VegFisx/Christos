# -*- coding: utf-8 -*-
r"""条件包络：这个模板在过去被观测到的时候，是在什么温度/时间下用的？

来源：reports/template_conditions.json（由 tools/build_template_conditions.py 从
      reports/ord_condition_dataset/*.parquet 抽出，模板 → 温度/时间分布/溶剂/催化剂）。

用法：
    from conditions import envelope
    fit, why = envelope.condition_fit(smarts, cond)

口径：
  * 温度在观测过的 [min, max] 内 → 1.0；超出去按 exp(-d/40°C) 衰减。
  * 时间在观测过的 [min, max] 内 → 1.0；超出去按 exp(-|ln(比值)|/1.5) 衰减。
  * 两者都有观测时取几何平均；只有一项时用那一项。
  * 观测数 < MIN_OBS 或没有温度/时间记录 → 1.0（未知不罚）。
  * 溶剂/催化剂暂不参与（ORD 溶剂名太杂，先不动）。

这不是热力学定律，是「经验包络」：它回答的是「这类转化在文献里是不是在这个温度窗口
被做过」。没有观测不等于不可能，所以缺数据时一律放行。
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

_HERE = Path(__file__).resolve().parent
_DEFAULT = _HERE.parent / "reports" / "template_conditions.json"

MIN_OBS = 5          # 少于这么多观测就当未知
TAU_C = 40.0         # 温度超出区间后每 40 °C 衰减一个 e
TAU_LOG_T = 1.5      # 时间比值每差 e^1.5 倍衰减一个 e
GATE_FIT = 0.15      # 显式筛选时的默认门槛（≈ 温度超出 ~76 °C 且时间差 ~4.7 倍）

_DEFAULT_TYPES = _HERE.parent / "reports" / "envelope_types.json"

_CACHE: Optional[Dict[str, Any]] = None
_CACHE_PATH: Optional[str] = None
_TYPES: Optional[Dict[str, Any]] = None
_TYPES_PATH: Optional[str] = None


def _atom_sig(a):
    """反应中心原子的指纹；SMARTS 里没写的属性退化成默认值（0/False），这是已知近似。"""
    try:
        hs = a.GetTotalNumHs()
    except Exception:                              # noqa: BLE001
        hs = a.GetNumExplicitHs()
    return (a.GetSymbol(), a.GetFormalCharge(), a.GetDegree(),
            a.GetIsAromatic(), a.IsInRing(), hs)


def _bonds(mol):
    out, atoms = {}, {}
    for b in mol.GetBonds():
        a1, a2 = b.GetBeginAtom(), b.GetEndAtom()
        m1, m2 = a1.GetAtomMapNum(), a2.GetAtomMapNum()
        if m1 and m2:
            out[(min(m1, m2), max(m1, m2))] = b.GetBondTypeAsDouble()
        if m1:
            atoms[m1] = a1
        if m2:
            atoms[m2] = a2
    return out, atoms


def type_key(smarts: str) -> Optional[str]:
    """模板 SMARTS -> 反应中心类型签名（与 tools/build_envelope_type.py 同一套口径）。"""
    if not smarts or ">>" not in smarts:
        return None
    left_s, right_s = smarts.split(">>", 1)
    left, right = Chem.MolFromSmarts(left_s), Chem.MolFromSmarts(right_s)
    if left is None or right is None:
        return None
    lb, latch = _bonds(left)
    rb, ratph = _bonds(right)
    if not lb and not rb:
        return None
    formed = [k for k in rb if k not in lb or abs(rb[k] - lb[k]) > 0.01]
    broken = [k for k in lb if k not in rb or abs(lb[k] - rb[k]) > 0.01]
    if not formed and not broken:
        return None
    idx = set()
    for a, b in formed + broken:
        idx.add(a)
        idx.add(b)
    sig = []
    for n in sorted(idx):
        at = ratph.get(n) or latch.get(n)
        if at is not None:
            sig.append(_atom_sig(at))
    if not sig:
        return None
    return repr((len(formed), len(broken), tuple(sorted(sig))))


def load_types(path: Optional[str] = None) -> Dict[str, Any]:
    """按反应类型聚合的观测表（模板表只有 1.7% 覆盖率时的退路）。"""
    global _TYPES, _TYPES_PATH
    p = path or os.environ.get("CHEMCREACT_ENVELOPE_TYPES") or str(_DEFAULT_TYPES)
    if _TYPES is not None and _TYPES_PATH == p:
        return _TYPES
    try:
        with open(p, encoding="utf-8") as f:
            _TYPES = (json.load(f) or {}).get("types", {})
        _TYPES_PATH = p
    except Exception:                              # noqa: BLE001
        _TYPES = {}
        _TYPES_PATH = p
    return _TYPES


def load(path: Optional[str] = None) -> Dict[str, Any]:
    global _CACHE, _CACHE_PATH
    p = path or os.environ.get("CHEMCREACT_TEMPLATE_COND") or str(_DEFAULT)
    if _CACHE is not None and _CACHE_PATH == p:
        return _CACHE
    try:
        with open(p, encoding="utf-8") as f:
            _CACHE = json.load(f)
        _CACHE_PATH = p
    except Exception:
        _CACHE = {}
        _CACHE_PATH = p
    return _CACHE


def _t_score(t: float, lo: float, hi: float) -> Tuple[float, str]:
    if t < lo:
        d = lo - t
    elif t > hi:
        d = t - hi
    else:
        return 1.0, ""
    return math.exp(-d / TAU_C), f"温度 {t:.0f}°C 在观测区间 [{lo:.0f}, {hi:.0f}] 外 {d:.0f}°C"


def _tm_score(tm: float, lo: float, hi: float) -> Tuple[float, str]:
    if lo <= tm <= hi:
        return 1.0, ""
    near = lo if tm < lo else hi
    if tm <= 0 or near <= 0:
        return 1.0, ""
    r = abs(math.log(tm / near))
    return math.exp(-r / TAU_LOG_T), f"时长 {tm:.0f} min 在观测区间 [{lo:.0f}, {hi:.0f}] 外"


def condition_fit(smarts: str, cond: Any,
                  path: Optional[str] = None) -> Tuple[float, str]:
    """返回 (fit ∈ [0,1], 说明)。smarts 为模板原文。"""
    if not smarts:
        return 1.0, "无模板"
    env = load(path)
    e = env.get(smarts)
    hit = e
    if not e or int(e.get("n") or 0) < MIN_OBS:
        # 模板级查不到时退回「反应中心类型」表：中药路径的模板来自另一套挖掘池，
        # 逐字匹配只有 1.7%，按类型聚合后覆盖面才会起来（reports/envelope_types.json）。
        key = type_key(smarts)
        e = load_types().get(key) if key else None
        hit = e
        if not e or int(e.get("n") or 0) < MIN_OBS:
            return 1.0, "该模板与反应类型都无足够观测（不罚）"

    t = float(getattr(cond, "temperature", 0.0) or 0.0)
    tm = float(getattr(cond, "time_min", 0.0) or 0.0)

    parts = []
    scores = []
    if e.get("t_min") is not None and e.get("t_max") is not None:
        s, why = _t_score(t, float(e["t_min"]), float(e["t_max"]))
        scores.append(s)
        if why:
            parts.append(why)
    if e.get("tm_min") is not None and e.get("tm_max") is not None:
        s, why = _tm_score(tm, float(e["tm_min"]), float(e["tm_max"]))
        scores.append(s)
        if why:
            parts.append(why)
    if not scores:
        return 1.0, "该模板无温度/时间观测（不罚）"

    fit = 1.0
    for s in scores:
        fit *= s
    fit = fit ** (1.0 / len(scores))
    if not parts:
        parts.append(f"条件落在观测区间内（观测 {int(e['n'])} 次）")
    src = "模板" if hit is env.get(smarts) else "反应类型"
    return round(fit, 4), src + "：" + "；".join(parts)


def observed(smarts: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """调试用：拿到某模板的原始观测统计。"""
    return load(path).get(smarts)
