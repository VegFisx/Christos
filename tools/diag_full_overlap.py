# -*- coding: utf-8 -*-
r"""诊断：全量 E 自检失败 —— 砌块集合里有 37 个分子的 full InChIKey 出现在产物侧。

问题：canonical SMILES 说"不同分子"，InChI 说"同一分子"。谁对？
做法：把撞的 37 个分子原样打印出来，看它们到底是什么关系
      （互变异构？电荷分离？立体？）
输出 reports\overlap_diag.json + 屏幕摘要

用法: python diag_full_overlap.py [抽样产物数]
"""
import json
import sys
import time
from collections import Counter
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
from rdkit.Chem import rdMolDescriptors  # noqa: E402
from build_purchasable_blocks import (  # noqa: E402
    BIG, REPORTS, TSV_CORE, TSV_REAGENT, canon_key, split_cx,
    inchi_keys_with_timeout)
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = REPORTS / "overlap_diag.json"
CACHE = REPORTS / "_prod_smiles_cache.txt"


def load_blocks():
    rows = []
    for path in (TSV_CORE, TSV_REAGENT):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or line.startswith("smiles\t"):
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) == 9:
                    rows.append(p)
    return rows


def main():
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else 30000
    t0 = time.time()
    blk = load_blocks()
    print(f"砌块 {len(blk):,}")

    # 产物分子（缓存，避免每次重扫）
    if CACHE.exists():
        prod = set(CACHE.read_text(encoding="utf-8").splitlines())
        print(f"读缓存产物分子 {len(prod):,}")
    else:
        con = duckdb.connect()
        con.execute("SET memory_limit='1500MB'")
        con.execute("SET threads=2")
        cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
        prod = set()
        n = 0
        while True:
            rows = cur.fetchmany(4000)
            if not rows:
                break
            n += len(rows)
            for (blob,) in rows:
                rxn = reaction_pb2.Reaction()
                try:
                    rxn.ParseFromString(blob)
                except Exception:
                    continue
                cx = next((i.value for i in rxn.identifiers
                           if i.type == reaction_pb2.ReactionIdentifier.REACTION_CXSMILES
                           and i.value), None)
                if not cx:
                    continue
                sp = split_cx(cx)
                if sp is None:
                    continue
                for part in sp[2].split("."):
                    part = part.strip()
                    if part:
                        g = canon_key(part)
                        if g:
                            prod.add(g[0])
            if n % 400000 < 4000:
                print(f"   扫 {n:,}，唯一产物 {len(prod):,}  {time.time()-t0:.0f}s", flush=True)
        CACHE.write_text("\n".join(sorted(prod)), encoding="utf-8")
        print(f"产物分子 {len(prod):,}（{time.time()-t0:.0f}s）已缓存")

    # 砌块 IK
    bsmiles = [r[0] for r in blk]
    got, hung = inchi_keys_with_timeout(bsmiles, workers=10, chunk=500,
                                        chunk_timeout=120.0, label="[砌块]")
    full2smi = {}
    skel2smi = {}
    for r in blk:
        s = r[0]
        f = got.get(s, ("", ""))[0]
        sk = got.get(s, ("", ""))[1]
        if f:
            full2smi.setdefault(f, []).append((s, r[1], r[6], r[8]))
        if sk:
            skel2smi.setdefault(sk, []).append(s)
    print(f"砌块 full IK {len(full2smi):,}（挂死 {len(hung)}）")

    # 产物 IK（抽样或全量）
    import random
    random.seed(20261011)
    plist = sorted(prod)
    if n_sample and len(plist) > n_sample:
        plist = random.sample(plist, n_sample)
    pgot, phung = inchi_keys_with_timeout(plist, workers=10, chunk=500,
                                          chunk_timeout=120.0, label="[产物]")
    pfull2smi = {}
    for s, (f, sk) in pgot.items():
        if f:
            pfull2smi.setdefault(f, []).append(s)
    print(f"产物 full IK {len(pfull2smi):,}（抽样 {len(plist):,}，挂死 {len(phung)}）")

    inter = set(full2smi) & set(pfull2smi)
    print()
    print("=" * 88)
    print(f"★ full InChIKey 撞 {len(inter)} 个")
    print("=" * 88)
    recs = []
    for k in sorted(inter):
        b = full2smi[k][0]
        p = pfull2smi[k][0]
        bm = Chem.MolFromSmiles(b[0])
        pm = Chem.MolFromSmiles(p)
        bf = rdMolDescriptors.CalcMolFormula(bm) if bm else "?"
        pf = rdMolDescriptors.CalcMolFormula(pm) if pm else "?"
        same_smiles = (b[0] == p)
        # 检查是否互变异构（RDKit TautomerEnumerator 规范化后是否相同）
        taut_same = None
        try:
            from rdkit.Chem.MolStandardize import rdMolStandardize
            te = rdMolStandardize.TautomerEnumerator()
            taut_same = (Chem.MolToSmiles(te.Canonicalize(bm)) ==
                         Chem.MolToSmiles(te.Canonicalize(pm)))
        except Exception:
            pass
        recs.append({"inchikey": k, "block_smiles": b[0], "prod_smiles": p,
                     "block_formula": bf, "prod_formula": pf,
                     "identical_smiles": same_smiles,
                     "tautomer_equivalent": taut_same,
                     "block_count": b[2], "block_map_ratio": b[3],
                     "block_skel": b[1]})
    n_ident = sum(1 for r in recs if r["identical_smiles"])
    n_taut = sum(1 for r in recs if r["tautomer_equivalent"])
    print(f"   其中 canonical SMILES 完全相同 : {n_ident}")
    print(f"   互变异构体等价（RDKit 规范化）: {n_taut}")
    print(f"   其余                          : {len(recs)-n_ident-n_taut}")
    print()
    for r in recs[:20]:
        print(f"   {r['inchikey']}")
        print(f"      砌块 {r['block_smiles'][:78]}  ({r['block_formula']}, n={r['block_count']}, map={r['block_map_ratio']})")
        print(f"      产物 {r['prod_smiles'][:78]}  ({r['prod_formula']})")
        print(f"      identical={r['identical_smiles']}  tautomer_eq={r['tautomer_equivalent']}")
    OUT.write_text(json.dumps({"n_overlap": len(recs), "n_identical_smiles": n_ident,
                               "n_tautomer_equivalent": n_taut,
                               "n_sampled_products": len(plist),
                               "records": recs}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
