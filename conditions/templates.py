# -*- coding: utf-8 -*-
"""
chemreact 条件层：预置条件模板
==============================

对应项目简报 §7 列的 8 种：煎煮、水提、醇提、酸水解、碱水解、氧化、还原、酶催化。

数值分三类，出处逐条登记在 template_provenance.json（第 101 轮 A8）：
- **有同行评议文献**（cited）：炮制档 7 个，温度/时长来自论文原值或区间中值；
- **只有二手来源**（secondary）：炒焦、炒炭，来自教学/百科站区间；
- **工艺惯例**（convention）或物理常数（physics）：煎煮 100°C/60 min、醇提 78°C（乙醇沸点）、
  酸/碱水解、氧化、还原、酶催化等 —— 这些是「这类工艺长什么样」，**不是实测最优值**。

用户 2026-11-04 立的规矩（AGENTS 第十二节）：涉及底层反应逻辑的参数必须有参考文献；
没有出处的只能当惯例登记，不得用来判零、不得默认开启。
因此 `provenance_of(name)` 的 status 不参与任何门控计算，只用于展示与自检。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from model import Conditions  # noqa: E402  （见 model.py 顶部关于文件名的说明）

TEMPLATES: Dict[str, Conditions] = {
    "自定义": Conditions(
        solvent="water", temperature=25, time_min=60, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "煎煮": Conditions(
        solvent="water", temperature=100, time_min=60, pH=6.5,
        catalyst=None, atmosphere="air",
    ),
    "水提": Conditions(
        solvent="water", temperature=60, time_min=120, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "醇提": Conditions(
        solvent="ethanol", temperature=78, time_min=120, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "酸水解": Conditions(
        solvent="water", temperature=100, time_min=120, pH=1.5,
        catalyst="acid", atmosphere="air",
    ),
    "碱水解": Conditions(
        solvent="water", temperature=100, time_min=120, pH=12.0,
        catalyst="base", atmosphere="air",
    ),
    "氧化": Conditions(
        solvent="water", temperature=100, time_min=240, pH=7.0,
        catalyst=None, atmosphere="O2",
    ),
    "还原": Conditions(
        solvent="water", temperature=60, time_min=240, pH=7.0,
        catalyst="metal", atmosphere="H2",
    ),
    "酶催化": Conditions(
        solvent="water", temperature=37, time_min=1440, pH=6.0,
        catalyst="enzyme", atmosphere="air",
    ),
    # 两个极端对照，方便做实验
    "室温浸泡": Conditions(
        solvent="water", temperature=25, time_min=1440, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "无氧煎煮": Conditions(
        solvent="water", temperature=100, time_min=60, pH=6.5,
        catalyst=None, atmosphere="N2",
    ),
    # 2026-10-31：无溶剂（炮制）。干热、不加溶剂，用于炒/烘等炮制场景；
    # 温度取 150°C（炒制常见区间 120–180°C），时长 30 min，pH 7 仅占位（无液相）。
    "无溶剂（炮制）": Conditions(
        solvent="none", temperature=150, time_min=30, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    # 2026-10-31：按文献拆分的炮制方法档。数值来源见
    # reports/paper/paozhi_sources_20261031.json；未建模项在 notes 里说明。
    "炮制·炒黄": Conditions(
        solvent="none", temperature=165, time_min=10, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "炮制·炒焦": Conditions(
        solvent="none", temperature=195, time_min=10, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "炮制·炒炭": Conditions(
        solvent="none", temperature=260, time_min=35, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "炮制·蜜炙": Conditions(
        solvent="none", temperature=120, time_min=13.5, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    # 酒炙：柴胡 黄酒 10%、135–145°C、5 min（中国医院药学杂志 2018）；
    # 醋炙：延胡索 米醋 37%、84°C、35 min（Biomed Chromatogr 2026）。
    "炮制·酒炙": Conditions(
        solvent="ethanol", temperature=140, time_min=5, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    "炮制·醋炙": Conditions(
        solvent="water", temperature=84, time_min=35, pH=3.0,
        catalyst=None, atmosphere="air",
    ),
    # 盐炙：药典通则 0213 每 100 kg 用食盐 2 kg；温度/时间取杜仲盐炙
    # 2% 盐水、150°C、10 min（药物分析杂志 2009, 29(11):1817–1820）。
    # 其他报道：沙苑子 2% 盐水 100°C/15 min（中草药 2025）；菟丝子 100°C/4 min。
    "炮制·盐炙": Conditions(
        solvent="water", temperature=150, time_min=10, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    # 姜炙：药典通则 0213 每 100 kg 用生姜 10 kg（干姜为 1/3）；
    # 温度/时间取黄连姜炙 15% 姜汁、150°C、40 min（中国药师 2016）。
    # 其他报道：厚朴 10% 姜汁 170°C/6 min；栀子 10% 姜汁 4.5 min。
    "炮制·姜炙": Conditions(
        solvent="water", temperature=150, time_min=40, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    # 蒸制：Piao 2020 红参 95–100°C、2–3 h；这里用 100°C/120 min。
    # 蒸汽未单独建模，用液态水 100°C 近似（已在 processing.notes 标注）。
    "炮制·蒸制": Conditions(
        solvent="water", temperature=100, time_min=120, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
    # 炮制·自定义（2026-11-06 用户要求）：默认不给固定工艺，条件由用户从界面
    # 或命令行填（--solvent/--temperature/--time-min/--ph/--atmosphere）。
    # 下面这组只是「引擎需要完整 Conditions」的占位基线：干热、无溶剂、150°C、
    # 30 min、常压空气。用户填了哪个就覆盖哪个，没填的沿用这组占位值。
    # 注意：它同样走炮制严格模式（只跑 rules/paozhi_evidence.json 的证据规则），
    # 但不加载任何辅料共底物——辅料需要用户先在工艺里说明，见 --no-paozhi-adjuvant。
    "炮制·自定义": Conditions(
        solvent="none", temperature=150, time_min=30, pH=7.0,
        catalyst=None, atmosphere="air",
    ),
}


_PROV_PATH = _HERE / "template_provenance.json"
_PROV: Dict[str, dict] = {}


def _load_provenance() -> Dict[str, dict]:
    """读 template_provenance.json；文件缺失时返回空表（不阻断主流程）。"""
    global _PROV
    if _PROV:
        return _PROV
    try:
        import json
        data = json.loads(_PROV_PATH.read_text(encoding="utf-8"))
        _PROV = dict(data.get("templates") or {})
    except Exception:                     # noqa: BLE001
        _PROV = {}
    return _PROV


def provenance_of(name: str) -> Dict[str, str]:
    """返回某个模板的出处标签，例如 {'status': 'cited', 'doi': '10.1002/bmc.70636'}。

    status 取值见 template_provenance.json 的 status_vocabulary：
    cited / secondary / convention / physics。查不到时返回 status='unknown'。

    2026-11-06 起额外带 `verified` 字段：联网逐条核对的结果（见
    template_verification_20261106.json），取值 supported / approximate /
    not_found / mismatch；只做登记，不改任何数值、不参与门控。
    """
    info = _load_provenance().get(name) or {}
    ver = verification_of(name)
    if not info:
        return {"status": "unknown", "note": "",
                "verified": str(ver.get("status") or "")}
    doi = ""
    for c in info.get("citations") or []:
        s = c.get("source") or {}
        if s.get("doi"):
            doi = s["doi"]
            break
        if s.get("url"):
            doi = s["url"]
    return {"status": str(info.get("status") or "unknown"),
            "match": str(info.get("match") or ""),
            "doi": doi,
            "note": str(info.get("note") or ""),
            "verified": str(ver.get("status") or "")}


_VER_PATH = _HERE / "template_verification_20261106.json"
_VER: Dict[str, dict] = {}


def _load_verification() -> Dict[str, dict]:
    """读 2026-11-06 的联网核对表；缺文件时返回空表。"""
    global _VER
    if _VER:
        return _VER
    try:
        import json
        data = json.loads(_VER_PATH.read_text(encoding="utf-8"))
        _VER = {str(e.get("template")): e for e in (data.get("entries") or [])}
    except Exception:                     # noqa: BLE001
        _VER = {}
    return _VER


def verification_of(name: str) -> Dict[str, dict]:
    """返回某个模板的联网核对结果（status / preset / found[] / verdict_note）。"""
    info = _load_verification().get(name) or {}
    return info if isinstance(info, dict) else {}


_TAG = {"cited": "[文献]", "secondary": "[二手]", "convention": "[惯例]",
        "physics": "[常数]", "unknown": "[未登记]"}


def list_templates() -> str:
    lines = ["可用的条件模板：", ""]
    for name, c in TEMPLATES.items():
        p = provenance_of(name)
        lines.append(f"  {name:<8} {_TAG.get(p['status'], '[未登记]')} {c.describe()}")
    lines += ["", "出处明细见 conditions/template_provenance.json（含 DOI 与引句）。"]
    return "\n".join(lines)


def get_template(name: str) -> Conditions:
    if name not in TEMPLATES:
        raise KeyError(f"没有条件模板 {name!r}，可用：{sorted(TEMPLATES)}")
    return TEMPLATES[name]
