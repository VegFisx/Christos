# -*- coding: utf-8 -*-
"""
chemreact 条件层：预置条件模板
==============================

对应项目简报 §7 列的 8 种：煎煮、水提、醇提、酸水解、碱水解、氧化、还原、酶催化。

这些不是拍脑袋写的：
- 煎煮 = 100°C 水、常压、有氧、约 1 小时 —— 中药汤剂的标准工艺
- 醇提 = 乙醇回流 78°C（乙醇沸点）—— 提取亲脂性成分
- 酸/碱水解 = 加酸加碱 + 长时间加热 —— 刻意打断糖苷/酯键
- 氧化 = 通氧或暴露空气 + 长时间 —— 多酚氧化、醌类生成
- 还原 = 氢气氛围 —— 煎煮条件下**几乎不会发生**，模板留着是为了对比实验
- 酶催化 = 37°C 近中性 + 长时间 —— 模拟体内/发酵
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
}


def list_templates() -> str:
    lines = ["可用的条件模板：", ""]
    for name, c in TEMPLATES.items():
        lines.append(f"  {name:<8} {c.describe()}")
    return "\n".join(lines)


def get_template(name: str) -> Conditions:
    if name not in TEMPLATES:
        raise KeyError(f"没有条件模板 {name!r}，可用：{sorted(TEMPLATES)}")
    return TEMPLATES[name]
