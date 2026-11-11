# -*- coding: utf-8 -*-
"""压力对液相的约束：沸点上限（压力 P2）。

**只做一件事**：密闭体系里，液相温度不会超过该压力下的沸点。所以
`T_eff = min(T, T_sat(p))`，`T_eff` 再进现有的 Arrhenius/Q10 温度因子。

## 为什么用 Clausius–Clapeyron 而不是 Antoine

Antoine 每溶剂一套系数、适用区间还不一样，多一张表就多一处抄错的机会。
Clausius–Clapeyron 只需要两个物理量（常压沸点 Tb、汽化焓 ΔHvap），
1 atm 处天然精确（T(p_b)=Tb，不用任何拟合），在 0.05~5 atm 内误差 <1 °C
（水：2 atm 算 120.8 °C，Antoine/实测 120.5 °C）。

    ln(p / p_b) = -(ΔHvap / R) · (1/T - 1/Tb)

数据：CRC Handbook of Chemistry and Physics, 97th ed.,
"Physical Constants of Organic Compounds"（Tb、ΔHvap 两列）。
只登记生产条件里真的会用到的溶剂；未登记的返回 None（不猜）。

## 不覆盖（写在这里免得以后当成 bug）

1. **ΔV‡ 效应**（压力直接改变速率/选择性）：需要活化体积或同一反应的
   压力序列数据；ORD 数据集没有压力列（178 片 925,943 行实测）。
2. **超临界 / 近临界**：Clausius–Clapeyron 在临界点附近失效。
3. **混合溶剂**：按主溶剂算，不按摩尔分数修正活度。
4. **辅料润湿**：酒炙/盐炙/姜炙靠的是「药材被辅料打湿」而不是「泡在液体里」，
   其温度是锅温不是液温，所以**不受沸点上限约束**（见 `BATH_WETTING`）。
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

R_GAS = 8.314462618  # J/(mol·K)，与 kinetics.json 的 arrhenius.R 同值

# 常压沸点（°C）与汽化焓（kJ/mol）。CRC Handbook 97th ed. 表格值。
SOLVENTS: Dict[str, Dict[str, float]] = {
    "water":       {"Tb_C": 100.0, "dHvap_kJ": 40.65},
    "methanol":    {"Tb_C": 64.7,  "dHvap_kJ": 35.21},
    "ethanol":     {"Tb_C": 78.3,  "dHvap_kJ": 38.56},
    "isopropanol": {"Tb_C": 82.6,  "dHvap_kJ": 45.39},
    "acetone":     {"Tb_C": 56.1,  "dHvap_kJ": 31.30},
    "mecn":        {"Tb_C": 82.0,  "dHvap_kJ": 33.16},
    "dcm":         {"Tb_C": 39.6,  "dHvap_kJ": 28.06},
    "chcl3":       {"Tb_C": 61.2,  "dHvap_kJ": 29.24},
    "thf":         {"Tb_C": 66.0,  "dHvap_kJ": 31.99},
    "et2o":        {"Tb_C": 34.6,  "dHvap_kJ": 27.10},
    "etoac":       {"Tb_C": 77.1,  "dHvap_kJ": 35.58},
    "toluene":     {"Tb_C": 110.6, "dHvap_kJ": 37.98},
    "benzene":     {"Tb_C": 80.1,  "dHvap_kJ": 33.83},
    "hexane":      {"Tb_C": 68.7,  "dHvap_kJ": 31.56},
    "dmso":        {"Tb_C": 189.0, "dHvap_kJ": 52.55},
    "dmf":         {"Tb_C": 153.0, "dHvap_kJ": 46.90},
    "dioxane":     {"Tb_C": 101.1, "dHvap_kJ": 35.79},
    "pyridine":    {"Tb_C": 115.2, "dHvap_kJ": 40.54},
}

# 粗类别 → 代表溶剂（拿得到沸点的情况）
COARSE_AS = {
    "aqueous": "water",
    "water": "water",
    "alcohol": "ethanol",
}

# ★ 浴类型：只有「泡在液体里」的才受沸点上限约束
BATH_DRY = {                      # 无溶剂干热：锅温，不是液温
    "无溶剂（炮制）", "炮制·炒黄", "炮制·炒焦", "炮制·炒炭",
    "炮制·蜜炙", "炮制·自定义",
}
BATH_WETTING = {                  # 辅料润湿：表面一层液体，主体是锅温
    "炮制·酒炙", "炮制·盐炙", "炮制·姜炙",
}
BATH_STEAM = {"炮制·蒸制"}         # 蒸汽：100 °C 由常压沸点定

DEFAULT_PARAMS = {
    "enabled": True,
    "note": "T_eff = min(T, T_sat(p))，只对溶液浴生效",
}

_PARAMS_CACHE: Dict[str, Any] = {}


def _params(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if params is not None:
        blk = dict(DEFAULT_PARAMS)
        blk.update({k: v for k, v in (params.get("pressure_ceiling") or {}).items()
                    if v is not None})
        return blk
    cached = _PARAMS_CACHE.get("p")
    if cached is not None:
        return cached
    try:
        from conditions.extent import load_params as _load  # 避免循环导入
        p = _load()
    except Exception:
        p = {}
    blk = dict(DEFAULT_PARAMS)
    blk.update({k: v for k, v in ((p or {}).get("pressure_ceiling") or {}).items()
                if v is not None})
    _PARAMS_CACHE["p"] = blk
    return blk


def bath_of(cond: Any) -> str:
    """这次处理是哪种「浴」：solution / steam / wetting / dry。

    优先看条件模板名（`Conditions.template`），模板名缺失时退回溶剂。
    """
    name = str(getattr(cond, "template", "") or "")
    if name in BATH_DRY:
        return "dry"
    if name in BATH_WETTING:
        return "wetting"
    if name in BATH_STEAM:
        return "steam"
    solvent = str(getattr(cond, "solvent", "") or "").strip().lower()
    if solvent in ("", "none"):
        return "dry"
    return "solution"


def _solvent_key(solvent: str) -> Optional[str]:
    s = str(solvent or "").strip().lower()
    if not s:
        return None
    if s in SOLVENTS:
        return s
    parent = COARSE_AS.get(s)
    return parent if parent in SOLVENTS else None


def t_sat_C(solvent: str, pressure_atm: float) -> Optional[float]:
    """该溶剂在给定压力下的沸点（°C）。不知道这个溶剂就返回 None（不猜）。"""
    hit = SOLVENTS.get(_solvent_key(solvent) or "")
    if not hit:
        return None
    try:
        p = float(pressure_atm)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    tb_k = float(hit["Tb_C"]) + 273.15
    dh = float(hit["dHvap_kJ"]) * 1000.0
    if dh <= 0:
        return None
    try:
        inv = 1.0 / tb_k - (R_GAS * math.log(p)) / dh
    except (ValueError, ZeroDivisionError):
        return None
    if inv <= 0:
        return None
    return 1.0 / inv - 273.15


def effective_temperature(cond: Any,
                          params: Optional[Dict[str, Any]] = None,
                          ) -> Tuple[float, str]:
    """返回 (T_eff, 说明)。不受约束时 T_eff == cond.temperature，说明为空串。"""
    T = float(getattr(cond, "temperature", 100.0))
    blk = _params(params)
    if not blk.get("enabled", True):
        return T, ""
    bath = bath_of(cond)
    if bath in ("dry", "wetting"):
        return T, ""
    p = float(getattr(cond, "pressure_atm", 1.0) or 1.0)
    tsat = t_sat_C(str(getattr(cond, "solvent", "") or ""), p)
    if tsat is None:
        return T, ""
    if T <= tsat:
        return T, ""
    solvent = str(getattr(cond, "solvent", "") or "?")
    return tsat, (f"液相沸点上限：{solvent} @ {p:g} atm 沸点 {tsat:.1f}°C，"
                  f"设定 {T:g}°C 截断为 {tsat:.1f}°C（压力 P2）")
