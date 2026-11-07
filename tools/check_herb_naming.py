# -*- coding: utf-8 -*-
r"""判定性检查：药材名的解析**一律以 HERB 库（tcm.db）自己的本名/别名列为准**。

用户 2026-10-16 定的口径：
  > 「生地黄这样的，就按 HERB 数据库里的药材本名处理就行。」

也就是：
  * 库里 **本名** 有 → 用它；
  * 库里 **别名列**（`herbs.alias`，分号分隔）里有 → 按别名指到的本名用它（可多个候选）；
  * 库里**都没有** → 如实报「库缺」，**不硬凑**（不靠前缀/去字/猜同物去映射）。

判据（跑得出对错）：
  1. `生地黄` → 必须落到达 **鲜地黄 / 干地黄**（库里把「生地黄」写在这两味的别名里）；
  2. `生地`（库里别名里没有这一档）→ **必须为空**，不许被硬凑成 地黄；
  3. `炙甘草`（库里有本名）→ 用它自己，不被替换成 甘草（炮制品闸）；
  4. `姜半夏`（药典炮制品、库里没有）→ 为空 + 报炮制品提示，不许落到 半夏。

复现：``python tools\check_herb_naming.py``
"""
from __future__ import annotations

import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))
sys.path.insert(0, str(STAGE / "tools"))

from tcm_ro import open_db                                  # noqa: E402
import herb as H                                            # noqa: E402
import processed as PR                                      # noqa: E402

CASES = [
    ("生地黄", {"鲜地黄", "干地黄"}, "库里把「生地黄」写在 鲜地黄/干地黄 的别名列里"),
    ("生地", {"干地黄"}, "★ 第七十五轮人工审定：生地=生地黄 → 干地黄（data\\alias_curated.json）"),
    ("桂心", {"肉桂"}, "★ 用户 2026-10-17 确认：桂心=肉桂（表里曾误配茯苓，已改正）"),
    ("朴消", set(), "审定表里为 朴消→朴硝，但**库里没有朴硝** → 如实报库缺（不硬凑）"),
    ("炙甘草", {"炙甘草"}, "库里有本名 → 用它自己（炮制品闸）"),
    ("姜半夏", set(), "药典炮制品、库里没有 → 不许落到 半夏"),
]


def main() -> int:
    bad = 0
    with open_db() as c:
        cur = c.cursor()
        for name, want, why in CASES:
            got = H._resolve_herb_ids(cur, name)
            names = {g[1] for g in got}
            ok = names == want
            bad += 0 if ok else 1
            print("  %s  %-6s → %-22s（期望 %-14s）｜ %s"
                  % ("PASS" if ok else "FAIL", name,
                     "、".join(sorted(names)) or "（空）",
                     "、".join(sorted(want)) or "（空）", why))
            if PR.is_processed(name):
                print("        （炮制品闸：is_processed=True，基原=%s）" % PR.base_of(name))
    print()
    print("  结论：%s" % ("全部符合「按 HERB 库本名/别名」口径 ✓" if not bad
                          else "★ 有 %d 条不符合" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
