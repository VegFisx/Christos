# -*- coding: utf-8 -*-
r"""① 溶剂偏好表：用**带成败标签**的数据重建"每类反应在哪些溶剂里成功过"。

## 为什么重建
第三十四/三十五轮实测：引擎里 `B-H` 的偏好溶剂表是
`['toluene','water','1,4-dioxane','DMF','EtOH','EtOAc']` —— **DMSO 不在里面**，
而 DMSO 是 HTE 里这类偶联最常用的好溶剂（2,712/20,473 条）。
结果：引擎给最好的溶剂扣分 -> 成对 AUC 0.458（**方向是反的**）。

那张表是从 ORD"该类反应用过哪些溶剂"统计来的（**不管成败**，而且样本少）。
本脚本改用**带产率标签**的数据算"溶剂成功率"，并允许合并多个来源。

## 口径（先定死）
* 来源 1（有标签，优先级最高）：HTE 的 `BH_HTE_Curated_Dataset_v20260219.csv`
  —— 逐行有 Yield；按 `Solvent Name` 聚合：n、成功率（Yield≥0.5 占比）、中位产率
  —— 归属反应类：HTE 全是 Buchwald-Hartwig 类偶联 -> `B-H` 与 `cross_electrophile_coupling`
* 来源 2（无标签，只作补充）：ORD 条件表的 per-class `solvents`
  （保持"出现过的溶剂"，但标记 `has_outcome=false`）
* 输出：`reports/solvent_evidence.json`
    {"classes": {"B-H": {"solvents": [{"name","n","success_rate","median_yield",
                                        "has_outcome"}...], "source": ..., "n_total": ...}}}

用法:
    & $py -u tools\build_solvent_evidence.py
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "conditions", STAGE / "rules",
           STAGE / "tools", STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

CSV = (STAGE / "data" / "external" / "bh-hte-ood"
       / "schwallergroup-bh-hte-ood-a277041" / "data"
       / "BH_HTE_Curated_Dataset_v20260219.csv")
OUT = STAGE / "reports" / "solvent_evidence.json"
POS = 0.5
# HTE 记录的归属反应类：**只归给实测确认的那一个**。
# ★ 踩过的坑：第一版把统计同时归给 `B-H` 和 `cross_electrophile_coupling`（我以为都是偶联），
#   结果 `cross_electrophile_coupling` 在 THF 下被降权 -> 撞坏
#   `test_required_reagent_gate.py` 的"37 类全放行"向后兼容断言。
#   现在只在**有实测归属证据**时才归（见 tools/measure_hte_validation.py 的规则命中分布：
#   正例 60 组里 B-H 命中 62 次；cross_electrophile_coupling 也命中，但那是同批混淆的产物，
#   不足以作为"HTE 就是这一类"的证据）。
HTE_CLASSES = ("B-H",)


def main() -> int:
    t0 = time.time()
    if not CSV.exists():
        print(f"缺 {CSV}")
        return 2
    per_solvent = defaultdict(lambda: {"n": 0, "n_pos": 0, "yields": []})
    n_rows = 0
    with open(CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            name = str(row.get("Solvent Name", "")).strip()
            if not name:
                continue
            try:
                y = float(row.get("Yield") or 0.0)
            except ValueError:
                y = 0.0
            d = per_solvent[name]
            d["n"] += 1
            if y >= POS:
                d["n_pos"] += 1
            d["yields"].append(y)
            n_rows += 1
    print(f"HTE 行 {n_rows:,}（带产率标签），溶剂 {len(per_solvent)} 种")

    solvents = []
    for name, d in per_solvent.items():
        ys = sorted(d["yields"])
        solvents.append({
            "name": name,
            "n": d["n"],
            "success_rate": round(d["n_pos"] / d["n"], 4),
            "median_yield": round(statistics.median(ys), 4),
            "has_outcome": True,
        })
    solvents.sort(key=lambda x: (-x["n"], x["name"]))

    # ORD 侧（无标签）：只作为"该类用过它"的补充
    from smartreact_engine import SmartReactEngine
    eng = SmartReactEngine()

    classes = {}
    for cls in HTE_CLASSES:
        classes[cls] = {"source": "HTE(BH) 带产率标签", "n_total": n_rows,
                        "solvents": [dict(s) for s in solvents]}
        e = eng.cond_table.get(cls) or {}
        extra = [s for s in (e.get("solvents") or [])
                 if str(s).lower() not in {x["name"].lower() for x in solvents}]
        for s in extra:
            classes[cls]["solvents"].append({"name": str(s), "n": 0,
                                             "success_rate": None,
                                             "median_yield": None,
                                             "has_outcome": False})
        print(f"  {cls}: 带标签溶剂 {len(solvents)} 种 + ORD 补充 {len(extra)} 种")

    payload = {
        "what": "每类反应的溶剂证据：成功过哪些溶剂、各多少条、成功率多少",
        "caveat": ("带标签部分只来自 HTE（Buchwald-Hartwig 型偶联），"
                   "其余反应类没有带标签的溶剂数据；"
                   "`has_outcome=false` 的条目只表示'该类在 ORD 里用过'，不代表成败"),
        "n_rows": n_rows,
        "pos_threshold": POS,
        "classes": classes,
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n溶剂成功率（前 12，按条数）：")
    for s in solvents[:12]:
        print(f"  {s['name']:<22} n={s['n']:>5}  成功率 {s['success_rate']:.1%}  "
              f"中位产率 {s['median_yield']:.2f}")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
