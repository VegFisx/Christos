# -*- coding: utf-8 -*-
r"""导出「待抽查」清单：H2 抽检里判为 **查无 / 部分命中** 的那些条（带来源链接）。

给用户按出处抽查用（用户 2026-10-16：把这两类单独列一栏）。
输出：``reports\第七十五轮-H2-待抽查（查无+部分命中）.csv``（UTF-8-BOM，Excel 可直接开）
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
VERD = STAGE / "data" / "h2_verdicts_all.json"
SAMPLE = [STAGE / "data" / "h2_sample.json", STAGE / "data" / "h2_sample2.json"]
OUT = STAGE / "reports" / "第七十五轮-H2-待抽查（查无+部分命中）.csv"


def main() -> int:
    rows = json.loads(VERD.read_text(encoding="utf-8"))
    samp = {}
    for b, p in enumerate(SAMPLE, 1):
        for x in json.loads(p.read_text(encoding="utf-8"))["items"]:
            samp[(b, x["序号"])] = x
    todo = [r for r in rows if r["判定"] in ("查无", "部分命中")]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["序号", "方名", "出处（库内原样）", "抽检判定", "组成字面重合",
                    "来源链接", "说明", "库里组成"])
        for r in todo:
            s = samp.get((r.get("批次", 1), r["序号"]), {})
            w.writerow(["第%d批 #%03d" % (r.get("批次", 1), r["序号"]),
                        r["方名"], r["出处"], r["判定"], r["覆盖率"],
                        r["来源URL"], r["理由"], s.get("组成", "")])
    print("  待抽查 %d 条（查无 %d + 部分命中 %d）→ %s"
          % (len(todo), sum(1 for r in todo if r["判定"] == "查无"),
             sum(1 for r in todo if r["判定"] == "部分命中"), OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
