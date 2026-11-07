# -*- coding: utf-8 -*-
r"""H2 第二批 · 再抽 200 条（与第一批**不重叠**，固定种子，可复现）。

口径：总体仍是 `category` 缺失的那批（5,332 条）；先按 (方名, 记录序号) 排好序，
去掉第一批已抽中的 100 条，再用 `random.Random(20261017)` 抽 200 条。
两批合起来 = **n=300 的简单随机样本**（可用于把 Wilson 区间收窄）。

输出：`data\h2_sample2.json` + `reports\第七十五轮-H2-第二批-清单.csv`
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "sources"))
import formula as F                                          # noqa: E402

SEED = 20261017
N = 200
CSV_OUT = STAGE / "reports" / "第七十五轮-H2-第二批-清单.csv"
JSON_OUT = STAGE / "data" / "h2_sample2.json"
SAMPLE1 = STAGE / "data" / "h2_sample.json"


def main() -> int:
    db = F._load()
    rows = []
    for nm in sorted(db):
        for i, r in enumerate(db[nm]):
            if not str(r.get("category") or "").strip():
                rows.append((nm, i, r))
    first = {x["稳定序号"] for x in
             json.loads(SAMPLE1.read_text(encoding="utf-8"))["items"]}
    pool = [k for k in range(len(rows)) if k not in first]
    rng = random.Random(SEED)
    picked = sorted(rng.sample(pool, N))
    out = []
    for n, idx in enumerate(picked, 1):
        nm, i, r = rows[idx]
        out.append({"序号": n, "稳定序号": idx, "方名": nm, "记录序号": i,
                    "出处": str(r.get("chuchu") or ""), "组成": str(r.get("peifang") or ""),
                    "功效": str(r.get("gongxiao") or ""), "用法": str(r.get("yongfa") or ""),
                    "判定": "", "来源URL": "", "说明": ""})
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    JSON_OUT.write_text(json.dumps(
        {"seed": SEED, "n": N, "total": len(rows), "excluded_first_batch": len(first),
         "source": "D:\\TCMAI\\data\\formula_db.json（category 缺失 = AI 现查批）",
         "items": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 100)
    print("H2 第二批：种子 %d，池子 %d 条（总体 %d 减去第一批 %d），抽 %d 条"
          % (SEED, len(pool), len(rows), len(first), N))
    print("=" * 100)
    print("  清单 -> %s" % CSV_OUT)
    print("  数据 -> %s" % JSON_OUT)
    for x in out[:6]:
        print("   #%03d %-12s %-20s %s" % (x["序号"], x["方名"][:12],
                                           x["出处"][:20], x["组成"][:46]))
    rng2 = random.Random(SEED)
    assert sorted(rng2.sample(pool, N)) == picked, "抽样不可复现！"
    assert not (set(picked) & first), "与第一批重叠了！"
    print("  ✓ 可复现且与第一批 0 重叠")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
