# -*- coding: utf-8 -*-
r"""独立验证：purchasable_blocks*.tsv 是不是真的符合口径？

不重跑抽取，只读产物文件 + 重新扫 ORD 抽样，独立复核 4 件事：
  V1 文件能读、行数对得上 meta
  V2 抽样核对：【砌块确实在 ORD 反应物段出现】且【确实从未在产物段出现】
     （独立重扫 parquet 的【另外一段】区间，不复用抽取时的统计）
  V3 InChIKey 与 SMILES 自洽（重新算一遍 key，必须一致）
  V4 分子式与 SMILES 自洽（重新算 formula）
  V5 阈值口径核对：core 文件里每行 map_ratio>=0.5 且 n_mapped>=5

用法: python verify_purchasable_blocks.py [抽样条数]
"""
import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from build_purchasable_blocks import (  # noqa: E402
    BIG, REPORTS, TSV_ALL, TSV_CORE, TSV_REAGENT, META_OUT, canon_key, split_cx,
    MAP_RATIO_CORE, MAP_COUNT_CORE)

RDLogger.DisableLog("rdApp.*")

FIELDS = ["smiles", "inchikey_skeleton", "inchikey", "MW", "heavy_atoms", "formula",
          "n_as_reactant", "n_mapped_as_reactant", "map_ratio"]


def load_tsv(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.startswith("smiles\t"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != len(FIELDS):
                continue
            rows.append(dict(zip(FIELDS, parts)))
    return rows


def scan_side_range(start, n, workers=6):
    """独立扫 parquet 的 [start, start+n) 区间，返回 (reac_set, prod_set)。"""
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    con.execute(f"CREATE VIEW v AS SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
    rows = con.execute(f"SELECT reaction FROM v OFFSET {start} LIMIT {n}").fetchall()
    reac, prod = set(), set()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = []
        step = 2000
        for i in range(0, len(rows), step):
            futs.append(pool.submit(_side_worker, rows[i:i + step]))
        for fu in futs:
            r, p = fu.result()
            reac |= r
            prod |= p
    return reac, prod


def _side_worker(rows):
    from ord_schema.proto import reaction_pb2
    reac, prod = set(), set()
    for (blob,) in rows:
        rxn = reaction_pb2.Reaction()
        try:
            rxn.ParseFromString(blob)
        except Exception:
            continue
        cx = next((i.value for i in rxn.identifiers
                   if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES and i.value),
                  None)
        if not cx:
            continue
        sp = split_cx(cx)
        if sp is None:
            continue
        lhs, _mid, rhs = sp
        for side, seg, sink in (("R", lhs, reac), ("P", rhs, prod)):
            for part in seg.split("."):
                part = part.strip()
                if not part:
                    continue
                g = canon_key(part)
                if g:
                    sink.add(g[0])
    return reac, prod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60000, help="独立复扫的反应条数")
    ap.add_argument("--offset", type=int, default=900000, help="独立复扫起点")
    ap.add_argument("--sample", type=int, default=300, help="抽样核对条数")
    args = ap.parse_args()

    print("=" * 90)
    print("独立验证：可购砌块集合")
    print("=" * 90)
    checks = []
    meta = json.loads(META_OUT.read_text(encoding="utf-8"))
    allr = load_tsv(TSV_ALL)
    core = load_tsv(TSV_CORE)
    reag = load_tsv(TSV_REAGENT)
    print(f"  文件: 全集 {len(allr):,}  核心 {len(core):,}  试剂 {len(reag):,}")
    print(f"  meta: n_blocks_all={meta['n_blocks_all']:,} "
          f"n_blocks_core={meta['n_blocks_core']:,} n_reagents={meta['n_reagents']:,} "
          f"is_full={meta['is_full']}")
    checks.append(("V1 文件行数与 meta 一致",
                   len(allr) == meta["n_blocks_all"] and len(core) == meta["n_blocks_core"]
                   and len(reag) == meta["n_reagents"]))

    # V2 独立重扫另一段
    t0 = time.time()
    reac, prod = scan_side_range(args.offset, args.n)
    print(f"\n  V2 独立复扫 offset={args.offset:,} 共 {args.n:,} 条："
          f"反应物分子 {len(reac):,}，产物分子 {len(prod):,}  ({time.time()-t0:.0f}s)")
    # 抽样：从 core+reag 里随机抽
    import random
    random.seed(20261011)
    pool_smis = [r["smiles"] for r in allr]
    sample = random.sample(pool_smis, min(args.sample, len(pool_smis)))
    in_reac = sum(1 for s in sample if s in reac)
    in_prod = sum(1 for s in sample if s in prod)
    # 期望：抽样里的分子在这段里【要么在反应物侧、要么两侧都没出现】，绝不在产物侧
    print(f"     抽样 {len(sample)} 个砌块 -> 在反应物侧 {in_reac}，"
          f"在产物侧 {in_prod}（必须为 0）")
    checks.append((f"V2a 抽样砌块不出现在产物侧（命中 {in_prod}）", in_prod == 0))
    print(f"     说明：抽样里有 {len(sample)-in_reac} 个在这段没出现过（正常，"
          f"本段只有 {args.n:,}/{meta['n_reactions_scanned']:,} 条）")

    # V3/V4 自洽
    n_ik_bad = n_mw_bad = n_missing = 0
    ex_bad = []
    for r in core[:200] + reag[:200]:
        m = Chem.MolFromSmiles(r["smiles"])
        if m is None:
            n_missing += 1
            continue
        ik = Chem.MolToInchiKey(m)
        if ik != r["inchikey"]:
            n_ik_bad += 1
            if len(ex_bad) < 3:
                ex_bad.append((r["smiles"], r["inchikey"], ik))
        if abs(float(r["MW"]) - Descriptors.MolWt(m)) > 0.05:
            n_mw_bad += 1
        if rdMolDescriptors.CalcMolFormula(m) != r["formula"]:
            n_mw_bad += 1
    print(f"\n  V3 InChIKey 不一致 {n_ik_bad} / {len(core[:200])+len(reag[:200])}"
          f"   解析失败 {n_missing}")
    for e in ex_bad:
        print(f"       {e[0][:60]}  文件={e[1]}  重算={e[2]}")
    checks.append((f"V3 InChIKey 自洽（不一致 {n_ik_bad}）", n_ik_bad == 0))
    checks.append((f"V4 MW/分子式 自洽（不一致 {n_mw_bad}，解析失败 {n_missing}）",
                   n_mw_bad == 0 and n_missing == 0))

    # V5 阈值
    bad_thr = [r for r in core
               if float(r["map_ratio"]) < MAP_RATIO_CORE
               or int(r["n_mapped_as_reactant"]) < MAP_COUNT_CORE]
    bad_thr2 = [r for r in reag
                if float(r["map_ratio"]) >= MAP_RATIO_CORE
                and int(r["n_mapped_as_reactant"]) >= MAP_COUNT_CORE]
    print(f"\n  V5 阈值核对：core 越界 {len(bad_thr)}，reagents 越界 {len(bad_thr2)}")
    checks.append((f"V5 core/reagents 按阈值严格二分"
                   f"（{len(bad_thr)}/{len(bad_thr2)}）",
                   len(bad_thr) == 0 and len(bad_thr2) == 0))

    # V6 两个文件互斥且并集 = 全集
    s_all = {r["smiles"] for r in allr}
    s_core = {r["smiles"] for r in core}
    s_reag = {r["smiles"] for r in reag}
    checks.append((f"V6 core ∩ reagents = {len(s_core & s_reag)}，并集 = 全集"
                   f"（缺 {len(s_all - (s_core | s_reag))}）",
                   not (s_core & s_reag) and (s_core | s_reag) == s_all))

    print()
    print("=" * 90)
    ok_all = True
    for name, ok in checks:
        ok_all &= ok
        print(f"  {'OK ' if ok else 'XX '} {name}")
    print("=" * 90)
    print("★ 全部通过" if ok_all else "★ 有未通过项 —— 不要拿去用")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
