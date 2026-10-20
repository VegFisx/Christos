# -*- coding: utf-8 -*-
r"""**人工审定**的异名表（第七十五轮，用户 2026-10-17：ok=采纳 / 不对=否决）。

来源：`tools\mine_alias_from_versions.py` 从同名方剂多版本里挖出候选 → Top100 逐条人工判定
（13 条采纳 / 87 条否决，理由见 `reports\第七十五轮-异名候选-已判（Top100）.csv`）。

纪律：
  * 只收**同物异写/异名**（耆=芪、消=硝、官桂=肉桂…）；
  * **绝不**收炮制品→基原（姜半夏/清半夏/枯矾 等一律否决）；
  * 部分→全株的（归尾/归身→当归）在备注里标明；
  * 本模块只做**最后一道**兜底：`herb._resolve_herb_ids` / `formula._resolve_one` 在
    精确、DB 别名、模糊、外文名都失败后才查这里，命中会打上「别名(审定)」的来源标记。
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

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "alias_curated.json"
_CACHE: Optional[Dict[str, dict]] = None
_PATH = ""


def _load(path: Path = DEFAULT) -> Dict[str, dict]:
    global _CACHE, _PATH
    if _CACHE is None or _PATH != str(path):
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
            _CACHE = {x["alias"]: x for x in d.get("pairs") or []}
        except Exception as ex:                              # noqa: BLE001
            print("   [warn] alias_curated：读不到审定表（%s: %s）" % (type(ex).__name__, ex))
            _CACHE = {}
        _PATH = str(path)
    return _CACHE


def resolve(name: str, path: Path = DEFAULT) -> Optional[str]:
    """审定异名 → 正名；没有就 None。**不做任何猜测**。"""
    hit = _load(path).get(str(name or "").strip())
    return hit["canonical"] if hit else None


def why(name: str, path: Path = DEFAULT) -> str:
    hit = _load(path).get(str(name or "").strip())
    return hit.get("why", "") if hit else ""


def size(path: Path = DEFAULT) -> int:
    return len(_load(path))


def _selftest() -> int:
    print("审定异名 %d 条：" % size())
    for k in ("黄耆", "芒消", "官桂", "生地", "姜半夏", "桂心"):
        print("  %-6s → %s" % (k, resolve(k) or "（不采纳/不在表里）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
