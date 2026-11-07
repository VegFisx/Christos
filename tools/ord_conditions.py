# -*- coding: utf-8 -*-
r"""ORD 条件构造的**单一真相**：以后所有评测脚本都从这里取条件，不要再各写一份。

## 为什么要有这个文件（第二十七轮）
"口径各写一份"在本项目已经吃过亏：
  · 第十七轮的"门控误杀率 0.67%"是**条件里没有试剂**时测的（判据被后门跳过）；
  · 各评测脚本自己拼 `Conditions`，于是 `reagents` 一直是空的，而**必需试剂判零因此从不触发**；
  · 直到第二十五/二十六轮才把"非贡献组分 = 试剂"抽成 `co_reagents`（705,513 行 = 76.2%）。

本模块提供：
  · `contributing_split(reactants, product)` —— 把带映射的反应物拆成【底物】与【试剂(非贡献组分)】
  · `load_ord_cases(...)` —— 从分片 + `co_reagents` 里取用例（含温度/溶剂/试剂），口径写死
  · `build_conditions(...)` —— 统一构造 `Conditions`（气氛默认 air，试剂可开关）

跑法（自检）：& "D:\TCMAI\venv\Scripts\python.exe" tools\ord_conditions.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
# ★ duckdb 在 staging/libs 里 —— 必须在 import 之前加 sys.path
for _p in (STAGE / "libs", STAGE / "tools", STAGE / "core", STAGE / "conditions",
           STAGE / "rules"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import duckdb  # noqa: E402
from rdkit import RDLogger  # noqa: E402

import mapped_chem as mc  # noqa: E402
import model as M  # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
CO_REAGENTS = (STAGE / "reports" / "ord_co_reagents" / "shard_*.parquet").as_posix()
DEFAULT_SEED = 20261013

Case = Dict[str, Any]


def contributing_split(reactants: str, product: str) -> Tuple[List[str], List[str]]:
    """把带映射的反应物拆成 (底物, 试剂)。

    判据与 `forward_template_mining` / `co_reagents` 抽取完全一致：
      某组分映射原子的 **>50%** 出现在产物里 -> 底物；否则 -> 试剂（非贡献组分）。
    返回的是 `canon_plain` 后的 SMILES。
    """
    contrib: List[str] = []
    noncontrib: List[str] = []
    pm = mc.parse_plain(str(product)) if product else None
    if pm is None:
        return contrib, noncontrib
    pmaps = mc.map_nums(pm)
    if not pmaps:
        return contrib, noncontrib
    for p in [x for x in str(reactants or "").split(".") if x]:
        m = mc.parse_plain(p)
        if m is None:
            continue
        nums = mc.map_nums(m)
        cs = mc.canon_plain(p)
        if not cs:
            continue
        if nums and len(nums & pmaps) / len(nums) > 0.5:
            contrib.append(cs)
        else:
            noncontrib.append(cs)
    return sorted(set(contrib)), sorted(set(noncontrib))


def build_conditions(temperature_C, solvent_names, co_reagents,
                     with_reagents: bool = True, atmosphere: str = "air",
                     time_min: float = 60.0, pH: float = 6.5) -> M.Conditions:
    """统一构造条件。溶剂名映射到粗类别；温度缺失**不填 0**（填 100 ℃ 并标 source）。"""
    s = str(solvent_names or "").lower()
    if "water" in s or "h2o" in s:
        sol = "water"
    elif s:
        sol = s.split(";")[0].split(",")[0].strip() or "water"
    else:
        sol = "water"
    t = float(temperature_C) if temperature_C is not None and temperature_C == temperature_C else 100.0
    reag = tuple(x for x in str(co_reagents or "").split(";") if x) if with_reagents else ()
    return M.Conditions(solvent=sol, temperature=t, time_min=time_min, pH=pH,
                        atmosphere=atmosphere, reagents=reag)


def load_ord_cases(n: int = 60000, seed: int = DEFAULT_SEED,
                   need_contrib: Optional[int] = 2, cap: int = 1200) -> Tuple[List[Case], Dict[str, int]]:
    """取 ORD 用例。`need_contrib=None` 表示不限贡献组分数。

    返回 (cases, skip)；每个 case 含 keys:
      reaction_id / substrates / reagents / wants / temperature_C / solvent_names
    """
    if not list((STAGE / "reports" / "ord_co_reagents").glob("*.parquet")):
        raise FileNotFoundError("缺 reports/ord_co_reagents/ —— 先跑 tools/extract_co_reagents.py")
    con = duckdb.connect()
    df = con.execute(f"""
        WITH s AS (
            SELECT reaction_id, reactants, product, temperature_C, solvent_names
            FROM read_parquet('{SHARDS}')
            USING SAMPLE {n} ROWS (reservoir, {seed})
        ), c AS (SELECT reaction_id, co_reagents FROM read_parquet('{CO_REAGENTS}'))
        SELECT s.*, c.co_reagents FROM s LEFT JOIN c USING (reaction_id)
    """).fetchdf()

    cases: List[Case] = []
    skip: Dict[str, int] = {}
    for rid, lhs, rhs, temp, solv, co in zip(df["reaction_id"], df["reactants"],
                                             df["product"], df["temperature_C"],
                                             df["solvent_names"], df["co_reagents"]):
        subs, reag = contributing_split(lhs, rhs)
        if need_contrib is not None and len(subs) != need_contrib:
            k = f"贡献组分={len(subs)}"
            skip[k] = skip.get(k, 0) + 1
            continue
        wants = {mc.canon_plain(x) for x in str(rhs).split(".") if x.strip()}
        wants.discard(None)
        if not wants:
            skip["产物归一失败"] = skip.get("产物归一失败", 0) + 1
            continue
        cases.append({"reaction_id": rid, "substrates": subs,
                      "reagents": reag or [x for x in str(co or "").split(";") if x],
                      "wants": wants, "temperature_C": temp, "solvent_names": solv})
        if len(cases) >= cap:
            break
    return cases, skip


if __name__ == "__main__":
    print("自检：")
    lhs = "[CH3:1][C:2](=[O:3])[OH:4].[Na+:9].[OH-:10]"
    rhs = "[CH3:1][C:2](=[O:3])[O-:4]"
    print("  contributing_split:", contributing_split(lhs, rhs))
    cases, skip = load_ord_cases(n=5000, cap=20)
    print(f"  取到 {len(cases)} 条用例；skip={skip}")
    if cases:
        c = cases[0]
        print(f"  样例：底物 {c['substrates']}  试剂 {c['reagents'][:3]}  "
              f"T={c['temperature_C']} 溶剂={c['solvent_names']}")
        print("  条件：", build_conditions(c["temperature_C"], c["solvent_names"],
                                          ";".join(c["reagents"])).describe())
