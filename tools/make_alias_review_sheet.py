# -*- coding: utf-8 -*-
r"""把「异名→正名」候选做成**Excel 能直接圈**的确认表（Top N）。

输出：``reports\第七十五轮-异名候选-待确认（Top100）.csv``（UTF-8-BOM）
列：序号 / 异名 / 建议正名 / 票数 / 置信度 / 出现过的方名 / **你的决定（留空）**
在"你的决定"里填 `Y`（采纳）或 `N`（否决），我按它接进解析层。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
SRC = STAGE / "data" / "alias_candidates_from_versions.json"
OUT = STAGE / "reports" / "第七十五轮-异名候选-待确认（Top100）.csv"


def main() -> int:
    d = json.loads(SRC.read_text(encoding="utf-8"))
    rows = d["candidates"][:100]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["序号", "异名（库里对不上）", "建议正名", "票数", "置信度",
                    "出现过的方名（例子）", "你的决定（填 Y=采纳 / N=否决，空=待定）", "备注"])
        for i, x in enumerate(rows, 1):
            w.writerow([i, x["alias"], x["canonical"], x["votes"], x["confidence"],
                        "、".join(x.get("examples") or []), "", ""])
    print("  Top %d 候选 -> %s" % (len(rows), OUT))
    print("  用法：在「你的决定」里填 Y/N，剩下交给我接进解析层（默认关开关）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
