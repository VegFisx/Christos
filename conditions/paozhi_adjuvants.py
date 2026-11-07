# -*- coding: utf-8 -*-
"""炮制辅料共底物（P2 原型）
=========================

把蜂蜜（葡萄糖 / 果糖）、黄酒（乙醇）、米醋（乙酸）作为**共底物**加入炮制枚举，
而不只是改 pH / 溶剂。结构一律来自 `rules/paozhi_adjuvants.json`，该文件由
`tools/build_paozhi_adjuvants.py` 从 `D:/TCMAI/tcm.db` 只读生成（未手写 SMILES）。

开关（默认开；只在炮制档启用）：
  * 环境变量 `CHEMCREACT_PAOZHI_ADJUVANT=0` 关闭；
  * 桥接命令行 `--no-paozhi-adjuvant` 关闭（本次运行）；
  * 非炮制条件永远不加载。

作用范围：目前只登记蜜炙 / 酒炙 / 醋炙 三种有明确辅料化学组成的档；
盐炙（NaCl）与姜炙（姜汁多成分）暂不登记，避免把“离子/提取物”误当共底物。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

_HERE = Path(__file__).resolve().parent
_JSON = _HERE.parent / "rules" / "paozhi_adjuvants.json"

_OFF_VALUES = {"0", "false", "off", "no", "none"}


def enabled(override: bool | None = None) -> bool:
    if override is not None:
        return bool(override)
    return os.environ.get("CHEMCREACT_PAOZHI_ADJUVANT", "1").strip().lower() not in _OFF_VALUES


def load() -> Dict:
    try:
        return json.loads(_JSON.read_text(encoding="utf-8"))
    except Exception as ex:                      # noqa: BLE001 —— 缺失时安静退回空表
        print("   [warn] 炮制辅料表读取失败：%s: %s" % (type(ex).__name__, ex))
        return {"methods": {}}


def compounds_for(method: str) -> Tuple[Dict, ...]:
    """返回该方法登记的辅料共底物（可能为空元组）。"""
    item = (load().get("methods") or {}).get(method) or {}
    return tuple(item.get("compounds") or ())


def describe(method: str) -> List[Dict]:
    """meta 用：把辅料结构与来源原样列出来。"""
    item = (load().get("methods") or {}).get(method) or {}
    out = []
    for c in item.get("compounds") or ():
        out.append({
            "name": c.get("name_cn") or c.get("name_en"),
            "name_en": c.get("name_en"),
            "smiles": c.get("smiles"),
            "ingredient_id": c.get("ingredient_id"),
            "formula": c.get("formula"),
            "pubchem_id": c.get("pubchem_id"),
            "source": f"tcm.db:{item.get('herb_id')}:{item.get('adjuvant')}",
            "adjuvant": item.get("adjuvant"),
            "herb_id": item.get("herb_id"),
        })
    return out
