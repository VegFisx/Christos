# -*- coding: utf-8 -*-
r"""炮制品闸门：**药典收载的炮制品是独立药材，不许拆解成基原**（用户 2026-10-16 定）。

用户原话：「这些很明显有的对应的是炮制品的名字，而你直接给我对应到基元上了。
**炮制品就是炮制品，不要再映射了**。herb 数据库里有炮制品的化学成分信息，药典也有。」

所以：`制何首乌` / `姜半夏` / `大蓟炭` / `炙甘草` 这些名字，
    * 库里有 → 用它（精确命中，本来就优先）
    * 库里没有 → **如实报「库缺」**，**绝不**替换成 何首乌 / 半夏 / 大蓟 / 甘草，
      也**不走**物种兜底、别名、前缀后缀那几条"帮忙"的规则。

清单来自 ``tools/build_chp_processed.py``（药典名录 + 炮制标记 + **同物种**双判据，
已剔除「土木香→木香」「土茯苓→茯苓」这两个假阳性）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Optional

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "chp_processed.json"
_CACHE: Optional[dict] = None
_PATH = ""


def _load(path: Path = DEFAULT) -> dict:
    global _CACHE, _PATH
    if _CACHE is None or _PATH != str(path):
        try:
            _CACHE = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            _CACHE = {"names": [], "map": {}}
        _PATH = str(path)
    return _CACHE


def is_processed(name: str, path: Path = DEFAULT) -> bool:
    return str(name or "").strip() in set(_load(path).get("names") or [])


def base_of(name: str, path: Path = DEFAULT) -> str:
    ent: Dict = (_load(path).get("map") or {}).get(str(name or "").strip()) or {}
    return str(ent.get("base") or "")


def marker_of(name: str, path: Path = DEFAULT) -> str:
    ent: Dict = (_load(path).get("map") or {}).get(str(name or "").strip()) or {}
    return str(ent.get("marker") or "")


def all_names(path: Path = DEFAULT) -> list:
    return list(_load(path).get("names") or [])


def _selftest() -> int:
    print("炮制品 %d 个：%s" % (len(all_names()), all_names()))
    for k in ("姜半夏", "制何首乌", "炙甘草", "土木香", "土茯苓", "甘草"):
        print("  %-8s is_processed=%-5s 基原=%s"
              % (k, is_processed(k), base_of(k) or "—"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
