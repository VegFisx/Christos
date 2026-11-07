# -*- coding: utf-8 -*-
r"""深查（可选，约 5~10 分钟）：对【全部产物分子】算 InChIKey，复核砌块与产物零重叠。

单独跑，因为它要给 160 万+ 个产物算 InChIKey，不能让主管道卡住。
输出 reports\deep_verify_blocks.json

用法: python deep_verify_blocks.py
"""
import json
import sys
import time
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
from build_purchasable_blocks import (  # noqa: E402
    BIG, REPORTS, TSV_ALL, TSV_CORE, TSV_REAGENT, canon_key, _ik_worker)

OUT = REPORTS / "deep_verify_blocks.json"


def main():
    print("=" * 90, flush=True)
    print("深查：全部产物分子 vs 砌块集合（full InChIKey 必须零重叠）", flush=True)
    print("=" * 90, flush=True)
    t0 = time.time()

    # 1) 读砌块
    def load(path, ncol):
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or line.startswith("smiles\t"):
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) == ncol:
                    out.append(p)
        return out
    core = load(TSV_CORE, 9)
    reag = load(TSV_REAGENT, 9)
    full_blocks = {r[2] for r in core + reag if r[2]}
    skel_blocks = {r[1] for r in core + reag if r[1]}
    print(f"砌块 {len(core)+len(reag):,}（full IK {len(full_blocks):,}）", flush=True)

    # 2) 唯一产物分子
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
    from ord_schema.proto import reaction_pb2
    from build_purchasable_blocks import split_cx
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
                if not part:
                    continue
                g = canon_key(part)
                if g:
                    prod.add(g[0])
        if n % 200000 < 4000:
            print(f"   扫 {n:,} 条，唯一产物 {len(prod):,}  {time.time()-t0:.0f}s", flush=True)
    print(f"唯一产物分子 {len(prod):,}（{time.time()-t0:.0f}s）", flush=True)

    # 3) 算 InChIKey（并行，分批，边算边写盘以便粗看进度）
    pl = sorted(prod)
    from build_purchasable_blocks import inchi_keys_with_timeout
    got, hung = inchi_keys_with_timeout(pl, workers=10, chunk=500,
                                         chunk_timeout=120.0, label="[IK]")
    full_prod = {v[0] for v in got.values() if v[0]}
    skel_prod = {v[1] for v in got.values() if v[1]}
    print(f"   InChI 完成 {len(got):,}，挂死跳过 {len(hung):,}", flush=True)

    inter_full = full_blocks & full_prod
    inter_skel = skel_blocks & skel_prod
    res = {
        "n_products_unique": len(prod),
        "n_products_ik": len(full_prod),
        "n_blocks": len(full_blocks),
        "overlap_full_inchikey": len(inter_full),
        "overlap_skeleton": len(inter_skel),
        "examples_full_overlap": sorted(inter_full)[:20],
        "elapsed_sec": round(time.time() - t0, 1),
        "inchi_hung": len(hung),
        "verdict": "PASS" if not inter_full else "FAIL",
    }
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2), flush=True)
    print(f"-> {OUT}", flush=True)
    return 0 if not inter_full else 1


if __name__ == "__main__":
    sys.exit(main())
