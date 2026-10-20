# -*- coding: utf-8 -*-
r"""别名索引（**多候选**）—— 由 ``tools/build_alias_index.py`` 生成。

来源：NTU《中文药名同义词表》（50,562 行 / 四部权威辞典）+ ``tcm.db`` 的
``herbs.alias`` + 用户在 ``build_alias_map.py`` 里的手工整理。

与旧做法的区别：旧表把"一个别名对应多个规范名"的 **5,417** 个情形**强行选了一个**，
本模块**保留全部候选**并给出来源与权威度 —— 同一俗名在不同地区指不同植物是真实情况。

候选已排序：库内药材优先 → 辞典权威度（药典 > 中华本草 > 中药大辞典 >
全国中草药汇编）→ 出现次数。**只提供候选，不替用户决定。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "alias_index.json"
_CACHE: Optional[dict] = None
_PATH: str = ""


def _load(path: Path = DEFAULT) -> dict:
    global _CACHE, _PATH
    if _CACHE is None or _PATH != str(path):
        try:
            _CACHE = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            _CACHE = {"meta": {}, "by_alias": {}}
        _PATH = str(path)
    return _CACHE


def available() -> bool:
    return bool(_load().get("by_alias"))


def lookup(name: str, path: Path = DEFAULT) -> List[Dict]:
    """别名 → **全部候选**（已排序）；不是别名则返回 ``[]``。"""
    return list(_load(path).get("by_alias", {}).get(str(name or "").strip(), []))


def best_in_db(name: str, path: Path = DEFAULT) -> Optional[str]:
    """别名 → 首选候选里**能在药材库找到的那个**（找不到返回 ``None``）。"""
    for c in lookup(name, path):
        if c.get("in_db") and c.get("canonical"):
            return str(c["canonical"])
    return None


def in_db(name: str, path: Path = DEFAULT) -> List[Dict]:
    """只看能在药材库里落地的候选。"""
    return [c for c in lookup(name, path) if c.get("in_db")]


def stats(path: Path = DEFAULT) -> dict:
    return dict(_load(path).get("meta") or {})


def _selftest() -> int:
    print("别名索引 meta:", stats())
    for k in ("龙胆草", "十字草", "槐米", "生地", "元参", "川军", "甘草", "不存在的别名"):
        v = lookup(k)
        print("  %-10s → %s" % (k, " ｜ ".join(
            "%s%s" % (x["canonical"], "" if x["in_db"] else "（库外）") for x in v[:6])
            or "（不是别名）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
