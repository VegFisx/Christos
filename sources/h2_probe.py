# -*- coding: utf-8 -*-
r"""H2 抽检结论的查询层（第七十五轮 H2 的产物接入网页/台账）。

`data/h2_verdicts.json` 是 H2 对**固定种子抽中的 100 条**逐条核对的结论
（命中 / 部分命中 / 查无 + 来源链接 + 覆盖率 + 理由）。本模块把它做成
按 **(方名, 出处)** 的查询：网页里的"方剂版本表"因此能多一栏「抽检」。

★ 只做**展示**：不改选版、不改排序、不隐藏任何版本；没抽到的一律显示「未抽检」。

键的写法要注意：库里 `chuchu` 字段原样带着句号（如 `《叶氏女科》卷二。`），
所以匹配时两边都做一次**去首尾标点/空白**的归一（不改变展示用的原文）。
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

# ★ 合并版（两批 n=300，同一口径）—— 网页「抽检」栏读的就是它
DEFAULT = Path(__file__).resolve().parent.parent / "data" / "h2_verdicts_all.json"
_CACHE: Optional[Dict[tuple, dict]] = None
_PATH = ""


def _norm(s: str) -> str:
    return str(s or "").strip().strip("。．.、；;：:，, \t\r\n")


def _load(path: Path = DEFAULT) -> Dict[tuple, dict]:
    global _CACHE, _PATH
    if _CACHE is None or _PATH != str(path):
        try:
            rows = json.loads(Path(path).read_text(encoding="utf-8"))
            _CACHE = {(_norm(r.get("方名")), _norm(r.get("出处"))): r for r in rows}
        except Exception as ex:                              # noqa: BLE001
            print("   [warn] h2_probe：读不到抽检结论（%s: %s）→ 一律显示「未抽检」"
                  % (type(ex).__name__, ex))
            _CACHE = {}
        _PATH = str(path)
    return _CACHE


def verdict(name: str, source: str, path: Path = DEFAULT) -> Optional[dict]:
    """(方名, 出处) → 抽检结论；没抽到返回 None。"""
    return _load(path).get((_norm(name), _norm(source)))


def all_rows(path: Path = DEFAULT) -> list:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return []


def _selftest() -> int:
    rows = all_rows()
    print("H2 抽检结论 %d 条（两批合并，%s）" % (len(rows), DEFAULT.name))
    from collections import Counter
    print("  判定分布：", dict(Counter(r["判定"] for r in rows)))
    for nm, src in (("五苓散", "《痘科类编》卷三。"), ("丁香散", "《叶氏女科》卷二。"),
                    ("清暑汤", "《伤寒大白》卷二。"), ("甘草", "ETCM")):
        v = verdict(nm, src)
        print("  %-8s %-16s → %s" % (nm, src, (v or {}).get("判定", "未抽检")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
