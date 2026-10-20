# -*- coding: utf-8 -*-
r"""中文药名 → 物种拉丁名（来自药典 2025 药材条目的正文）。

用途：``tcm.db`` 里没有的**正经药材**（药典收载但库缺，实测 52 味；其中 40 味现有规则
已能落到基原，真正缺 12 味），靠这份映射接到 **COCONUT 物种路线**，照样有成分可跑。

实测覆盖：药典 617 味药材里 **547 条抓到拉丁学名**，**523 条在 COCONUT 命中物种**。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "herb_species.json"
_CACHE: Dict[str, dict] = {}
_PATH = ""


def _load(path: Path = DEFAULT) -> Dict[str, dict]:
    global _CACHE, _PATH
    if _PATH != str(path):
        try:
            _CACHE = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            _CACHE = {}
        _PATH = str(path)
    return _CACHE


def species_of(name: str, path: Path = DEFAULT) -> List[str]:
    """中文药名 → COCONUT 能认的物种名列表（已 fold 归一）；没有则 ``[]``。"""
    rec = _load(path).get(str(name or "").strip())
    return list(rec.get("species") or []) if rec else []


def latin_of(name: str, path: Path = DEFAULT) -> List[str]:
    rec = _load(path).get(str(name or "").strip())
    return list(rec.get("latin_raw") or []) if rec else []


def url_of(name: str, path: Path = DEFAULT) -> str:
    rec = _load(path).get(str(name or "").strip())
    return str(rec.get("url") or "") if rec else ""


def _selftest() -> int:
    d = _load()
    print("映射条数 = %d" % len(d))
    for k in ("杠板归", "蓝布正", "瓜子金", "金果榄", "甘草", "不存在的药"):
        print("  %-8s 物种=%s" % (k, species_of(k) or "（无）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
