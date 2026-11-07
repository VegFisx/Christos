# -*- coding: utf-8 -*-
r"""探针：ORD 每条反应记录的**元素收支 + 副产物信息**能不能当方向判据？

只回答三个问题（一次跑完，打印原始数据在前）：
  ① 分片里到底有哪些列（特别是 byproducts / elements 之类）
  ② 每条记录「底物侧 -> 产物侧」的元素差（H/O/N 增减）是什么形状
  ③ 37 类反应里，每类的元素收支中位数是什么样（够不够当方向判据）

口径：底物侧 = contributing_split() 出的【贡献组分】（映射原子进产物的那些），
      产物侧 = product 拆分后的所有组分；元素用 RDKit 分子式算。
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import median

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "core", STAGE / "tools"):
    sys.path.insert(0, str(_p))

import duckdb                                     # noqa: E402
from rdkit import Chem, RDLogger                  # noqa: E402
from rdkit.Chem import rdMolDescriptors           # noqa: E402

RDLogger.DisableLog("rdApp.*")

SHARDS = (STAGE / "reports" / "ord_condition_dataset" / "shard_*.parquet").as_posix()
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40000

ELEMS = ("C", "H", "O", "N")


def counts(smiles_list):
    out = {e: 0 for e in ELEMS}
    for s in smiles_list:
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        f = rdMolDescriptors.CalcMolFormula(m)
        import re
        for el, k in re.findall(r"([A-Z][a-z]?)(\d*)", f):
            if el in out:
                out[el] += int(k) if k else 1
    return out


def main() -> int:
    t0 = time.time()
    con = duckdb.connect()
    print("① 分片 schema：")
    cols = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{SHARDS}')").fetchall()
    for c in cols:
        print(f"   {c[0]:<22} {c[1]}")
    # 有没有副产物/元素列
    names = [c[0] for c in cols]
    for want in ("byproducts", "elements", "yield", "reaction_name", "classes"):
        print(f"   含 {want!r} 列: {want in names}")

    print(f"\n② 抽样 {N:,} 条，算底物侧/产物侧元素差 ...")
    rows = con.execute(
        f"SELECT reactants, product FROM read_parquet('{SHARDS}') LIMIT {N}").fetchall()
    from ord_conditions import contributing_split
    per = {e: [] for e in ELEMS}
    n_used = 0
    n_no_split = 0
    for lhs, rhs in rows:
        try:
            subs, reags = contributing_split(str(lhs), str(rhs))
        except Exception:
            n_no_split += 1
            continue
        prods = [x for x in str(rhs or "").split(".") if x.strip()]
        if not subs or not prods:
            n_no_split += 1
            continue
        cs, cp = counts(subs), counts(prods)
        n_used += 1
        for e in ELEMS:
            per[e].append(cp[e] - cs[e])

    print(f"可用 {n_used:,} 条（拆不出贡献组分 {n_no_split:,}）用时 {time.time()-t0:.1f}s")
    print(f"\n   元素差（产物侧 - 底物侧）分位数：")
    print(f"   {'元素':<4}{'中位数':>8}{'10%':>8}{'90%':>8}{'减小的比例':>12}")
    for e in ELEMS:
        v = sorted(per[e])
        if not v:
            continue
        n_neg = sum(1 for x in v if x < 0)
        print(f"   {e:<4}{median(v):>8.1f}{v[len(v)//10]:>8}{v[9*len(v)//10]:>8}"
              f"{n_neg/len(v):>11.1%}")

    # 单看 H 和 O 的组合：脱水缩合 = H 减、O 减
    n_dehyd = sum(1 for i in range(len(per["H"]))
                  if per["H"][i] < 0 and per["O"][i] < 0)
    n_hyd = sum(1 for i in range(len(per["H"]))
                if per["H"][i] > 0 and per["O"][i] > 0)
    n_same = sum(1 for i in range(len(per["H"]))
                 if per["H"][i] == 0 and per["O"][i] == 0)
    tot = max(1, len(per["H"]))
    print(f"\n   元素收支模式（实测）：")
    print(f"     H↘ O↘（脱水缩合形状）  {n_dehyd:>7,}  {n_dehyd/tot:>7.1%}")
    print(f"     H↗ O↗（水解/加成形状）  {n_hyd:>7,}  {n_hyd/tot:>7.1%}")
    print(f"     H= O=（只换骨架/取代）  {n_same:>7,}  {n_same/tot:>7.1%}")
    print(f"\n总用时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
