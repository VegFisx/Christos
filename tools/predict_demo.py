# -*- coding: utf-8 -*-
r"""端到端 demo：**从你自己的库里取分子 -> 预测产物**（产物不必在库里，预测本来就是新的）。

## 口径（按用户 2026-10-12 的纠正）
> 「产物不用一定能从数据库里找到，产物是预测的东西，完全可以不在数据库里面」

所以三个库（`tcm.db` / `coconut.db` / HERB）在本脚本里的角色是**输入分子的来源**，
**不是答案键**——不拿"产物是否命中数据库"当验证指标。
输出只诚实地标出引擎自己知道的信号：**反应类型、来源成分、条件匹配度(activation)、引擎分**。

## 用法
  & $py tools\predict_demo.py --herb 甘草 --limit 15 --top 25
  & $py tools\predict_demo.py --coconut 12 --top 25
  & $py tools\predict_demo.py --smiles "OCc1ccccc1,NCCc1ccc(O)cc1" --top 25
  & $py tools\predict_demo.py --herb 甘草 --cond 醇提
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "conditions", STAGE / "rules", STAGE / "libs",
           STAGE / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from engine import Compound                      # noqa: E402
from smartreact_engine import SmartReactEngine   # noqa: E402
import templates as T                            # noqa: E402

COCONUT_DB = Path(r"D:\TCMAI\coconut.db")


def from_herb(name: str, limit: int):
    from herb import compounds_of_herb
    out = compounds_of_herb(name, limit=limit)
    return [(c.name, c.smiles, "tcm.db") for c in out]


def from_coconut(n: int):
    if not COCONUT_DB.exists():
        print(f"找不到 {COCONUT_DB}")
        return []
    con = sqlite3.connect(f"file:{COCONUT_DB}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT name, smiles FROM compounds "
        "WHERE smiles IS NOT NULL AND smiles <> '' "
        "ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
    con.close()
    return [(str(nm or "?"), str(sm), "coconut.db") for nm, sm in rows]


def demo_via_base(mols, cond_name: str, top: int) -> int:
    """★ 共用底座模式 ★：枚举交给 `core/query_base.build_inventory`，demo 只负责显示。

    为什么要有这条：2026-10-13 起，正版枚举口径在 `query_base`（查询式交互的底座）。
    demo 原来自己调 `engine.step()`，两处代码会慢慢漂移。`--via-base` 让 demo
    直接吃底座的结果，从而**可验证两者一致**（也是以后合并的过渡态）。
    """
    import sys as _sys
    _sys.path.insert(0, str(STAGE / "tools"))
    import query_base as qb
    from smartreact_engine import CONDENSATION_CLASSES
    from model import solvent_class

    spec = qb.RunSpec(seeds=[(nm, sm, src) for nm, sm, src in mols],
                      cond_name=cond_name, rounds=1)
    inv = qb.build_inventory(spec, score=True)
    rows = [dict(r) for r in inv.paths if not r["is_byproduct"]]
    rows.sort(key=lambda r: -(r["score"] if isinstance(r["score"], float) else 0.0))
    is_water = solvent_class(getattr(inv.spec.cond(), "solvent", "") or "") in ("water", "aqueous")
    n_warn = sum(1 for r in rows if is_water and r["rule_name"] in CONDENSATION_CLASSES)
    types: dict = {}
    for r in inv.paths:
        types[r["rule_name"]] = types.get(r["rule_name"], 0) + 1

    print(f"\n  ★ 走共用底座（query_base.build_inventory）：与 query_engine.py 同一口径")
    for n in inv.stats.engine_notes:
        print(f"        {n}")
    print(f"  产物分子 {inv.stats.n_products} 个（主体 {len(rows)}）  出处路径 "
          f"{inv.stats.n_paths_kept} 条  涉及反应类型 {len(types)} 类  耗时 {inv.stats.seconds}s")
    print(f"  类型分布：{dict(sorted(types.items(), key=lambda kv: -kv[1]))}")
    if is_water and n_warn:
        print(f"  ⚠ 其中 {n_warn} 条是水相里的脱水缩合产物 → 方向很可能反了"
              f"（引擎缺热力学/水解模板，见报告）")
    print(f"\n  {'分':>6}{'激活':>7}{'方向':>6}  {'反应类型':<20}{'来源成分':<18}{'分子式':<20}SMILES")
    print("  " + "-" * 106)
    for r in rows[:top]:
        rev = "可逆" if r["reversible"] else ""
        print(f"  {r['score'] if isinstance(r['score'], float) else 0:>6.3f}"
              f"{float(r['activation']):>7.2f}{rev:>6}  {str(r['rule_name'])[:18]:<20}"
              f"{str(r['source_name'])[:16]:<18}{str(r['formula']):<20}"
              f"{str(r['product_smiles'])[:50]}")
    out = STAGE / "reports" / "demo_产物_共用底座.csv"
    import csv as _csv
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["score", "activation", "reversible", "rule_name", "source_name",
                    "source_herb", "formula", "mw", "heavy_atoms", "smiles"])
        for r in rows:
            w.writerow([r["score"], r["activation"], r["reversible"], r["rule_name"],
                        r["source_name"], r["source_herb"], r["formula"], r["mw"],
                        r["heavy_atoms"], r["product_smiles"]])
    print(f"\n  完整清单（{len(rows)} 条）-> {out}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--herb", default=None, help="药材名（tcm.db，如 甘草）")
    ap.add_argument("--coconut", type=int, default=0, help="从 COCONUT 随机取 n 个天然产物当底物")
    ap.add_argument("--smiles", default=None, help="直接给逗号分隔的 SMILES")
    ap.add_argument("--limit", type=int, default=15, help="药材成分上限")
    ap.add_argument("--cond", default="煎煮", help="条件模板名（如 煎煮 / 醇提）")
    ap.add_argument("--top", type=int, default=25, help="打印前 N 条产物")
    ap.add_argument("--via-base", action="store_true",
                    help="★走共用底座（query_base）★，与 query_engine.py 同一口径")
    a = ap.parse_args()

    if a.smiles:
        mols = [(f"输入{i+1}", s.strip(), "手输") for i, s in enumerate(a.smiles.split(",")) if s.strip()]
    elif a.herb:
        mols = from_herb(a.herb, a.limit)
    elif a.coconut:
        mols = from_coconut(a.coconut)
    else:
        ap.error("至少给一个输入来源：--herb / --coconut / --smiles")

    if not mols:
        print("没取到分子"); return 1

    if a.via_base:
        return demo_via_base(mols, a.cond, a.top)

    cond = T.get_template(a.cond)
    print("=" * 108)
    print(f"预测 demo   输入来源 {'tcm.db' if a.herb else ('coconut.db' if a.coconut else '手输')}"
          f"   条件 {cond.describe()}")
    print("=" * 108)
    print(f"  输入分子 {len(mols)} 个（前 8 个）：")
    for nm, sm, src in mols[:8]:
        print(f"    [{src}] {nm[:22]:<24} {sm[:64]}")
    if len(mols) > 8:
        print(f"    … 另有 {len(mols)-8} 个")

    t0 = time.time()
    eng = SmartReactEngine()                      # 当前默认：K1 双底物 + 单底物模板
    seeds = [Compound(smiles=sm, name=nm, herb=src) for nm, sm, src in mols]
    prods = eng.step(seeds, cond, round_no=1)
    dt = time.time() - t0

    # ★ 补一个真排序：step() 里不算分（打分本来在级联里做），这里用同一个 scorer 算
    from scorer import score_product
    from smartreact_engine import CONDENSATION_CLASSES
    from model import solvent_class
    is_water = solvent_class(getattr(cond, "solvent", "") or "") in ("water", "aqueous")
    for p in prods:
        rule = eng._rule_by_id.get(p.rule_id, {})
        try:
            base, _d = score_product(p.smiles, rule, p.activation,
                                     source_smiles=p.source_smiles)
        except Exception:
            base = 0.0
        p.score = round(base, 4)
        # ★ 方向性提示（建模判断，不是实测）：水相里的脱水缩合产物，方向可能反了
        p._dir_warn = bool(is_water and p.rule_name in CONDENSATION_CLASSES)

    rows = [p for p in prods if not p.is_byproduct]
    rows.sort(key=lambda p: -(p.score or 0))
    types = {}
    for p in prods:
        types[p.rule_name] = types.get(p.rule_name, 0) + 1
    n_mined = sum(1 for p in prods if str(p.rule_name).startswith("mined_"))
    n_warn = sum(1 for p in rows if getattr(p, "_dir_warn", False))

    print(f"\n  引擎：{eng.extra_template_note}")
    print(f"        {eng.mono_template_note}")
    print(f"  产物 {len(prods)} 个（主体 {len(rows)}）  涉及反应类型 {len(types)} 类  "
          f"其中自抽模板产物 {n_mined}（{n_mined/max(1,len(prods)):.1%}）  耗时 {dt:.1f}s")
    print(f"  类型分布（前 10）：{dict(sorted(types.items(), key=lambda kv: -kv[1])[:10])}")
    if is_water and n_warn:
        print(f"  ⚠ 其中 **{n_warn} 条是水相里的脱水缩合产物 → 方向很可能反了**"
              f"（水里该往水解走；引擎缺热力学/水解模板，见报告）")

    print(f"\n  {'分':>6}{'条件匹配':>9}{'方向':>6}  {'反应类型':<20}{'来源成分':<18}{'分子式':<20}SMILES")
    print("  " + "-" * 106)
    for p in rows[:a.top]:
        flag = "可疑" if getattr(p, "_dir_warn", False) else ""
        print(f"  {p.score or 0:>6.3f}{p.activation:>9.2f}{flag:>6}  {str(p.rule_name):<20}"
              f"{str(p.source_name)[:16]:<18}{str(p.formula):<20}{p.smiles[:50]}")

    out = STAGE / "reports" / f"demo_产物_{(a.herb or ('coconut' if a.coconut else 'smiles'))}.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["score", "activation", "rule_name", "source_name", "source_herb",
                    "formula", "mw", "heavy_atoms", "smiles"])
        for p in rows:
            w.writerow([p.score, p.activation, p.rule_name, p.source_name, p.source_herb,
                        p.formula, p.mw, p.heavy_atoms, p.smiles])
    print(f"\n  完整清单（{len(rows)} 条）-> {out}")
    print("\n  ⚠ 边界：这是**候选产物预测**（召回优先），不是「会不会发生」的判据；")
    print("     产物不必在 COCONUT/HERB/tcm.db 里 —— 预测出未知化合物是正常的。")
    print("     若要判据层面的结论，参见 reports/第二十七轮…报告.md 的命中率口径。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
