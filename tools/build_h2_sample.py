# -*- coding: utf-8 -*-
r"""H2 · 从「AI 现查」那批里**固定种子**抽 100 条，生成待核对清单。

口径（先定死，避免抽完再改口径）：
  * 总体 = `formula_db.json` 里 `category` 缺失的那批记录（= H1 的 tier 5，实测 5,332 条）；
  * 抽样单位 = **一条记录**（同一个方名下的多条记录各自独立，因为它们出处不同）；
  * 抽法 = 把 5,332 条按 (方名, 记录序号) 排序得到稳定序号，
    再用 `random.Random(20261016)`（种子就是任务下发日期）**无放回**抽 100 条；
  * 输出 = `reports\第七十五轮-AI古方抽检-清单.csv`（UTF-8-BOM，Excel 可直接开）
    + `data\h2_sample.json`（给报告生成器用）。

判定口径（三档，核对方逐条填）：
  * **命中**   = 方名 + 出处 + 组成三者能在公开源对上（组成的主药一致；剂量可不同）
  * **部分命中** = 方名/出处能对上，但组成明显不同；或方名能对上、出处对不上
  * **查无**   = 公开源里找不到这个方名，或找到的与出处/组成都对不上

复现：``python tools\build_h2_sample.py``
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

SEED = 20261016
N = 100
CSV_OUT = STAGE / "reports" / "第七十五轮-AI古方抽检-清单.csv"
JSON_OUT = STAGE / "data" / "h2_sample.json"


def main() -> int:
    db = F._load()
    rows = []                     # (方名, 记录序号, 记录)
    for nm in sorted(db):
        for i, r in enumerate(db[nm]):
            if not str(r.get("category") or "").strip():      # ★ AI 现查批
                rows.append((nm, i, r))
    total = len(rows)
    rng = random.Random(SEED)
    picked = rng.sample(range(total), N)
    picked.sort()
    out = []
    for n, idx in enumerate(picked, 1):
        nm, i, r = rows[idx]
        out.append({
            "序号": n, "稳定序号": idx, "方名": nm, "记录序号": i,
            "出处": str(r.get("chuchu") or ""), "组成": str(r.get("peifang") or ""),
            "功效": str(r.get("gongxiao") or ""), "用法": str(r.get("yongfa") or ""),
            "判定": "", "来源URL": "", "说明": "",
        })
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(
        {"seed": SEED, "n": N, "total": total, "no_replacement": True,
         "source": "D:\\TCMAI\\data\\formula_db.json（category 缺失 = AI 现查批）",
         "items": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("=" * 100)
    print("H2 · 固定种子抽样（seed=%d，总体 %d 条，抽 %d 条，无放回）" % (SEED, total, N))
    print("=" * 100)
    print("  清单 -> %s" % CSV_OUT)
    print("  数据 -> %s" % JSON_OUT)
    print()
    for x in out[:8]:
        print("   #%03d %-12s %-22s %s" % (x["序号"], x["方名"][:12],
                                           x["出处"][:22], x["组成"][:52]))
    print("   … 共 %d 条" % len(out))
    # 自检：同一种子必须得到同一批
    rng2 = random.Random(SEED)
    assert sorted(rng2.sample(range(total), N)) == picked, "抽样不可复现！"
    print("  ✓ 抽样可复现（同一种子两次结果一致）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
