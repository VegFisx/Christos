# -*- coding: utf-8 -*-
r"""诊断：为什么"砌块"与"产物"在 InChIKey 骨架层面会撞？（E 自检失败）

两个问题分开回答：
  ① 撞的是【立体异构体】还是【整分子相同】？-> 比 full InChIKey（同分子才算真问题）
  ② 数据里有多少【同一反应两侧出现同一分子】的怪例？

用法: python diag_block_product_overlap.py --pilot 20000
"""
import argparse
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
from build_purchasable_blocks import parse_rows, _ik_worker, BIG, split_cx, canon_key  # noqa: E402
from ord_schema.proto import reaction_pb2  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=20000)
    args = ap.parse_args()

    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    cur = con.execute(f"SELECT reaction FROM read_parquet('{BIG.as_posix()}')")
    rows = cur.fetchmany(args.pilot)
    t0 = time.time()
    cnt, mp, stat = parse_rows(rows)
    print(f"解析 {len(rows):,} 条，{time.time()-t0:.1f}s")

    prod = {k for (k, s) in cnt if s == "P"}
    reac = {k for (k, s) in cnt if s == "R"}
    blocks = reac - prod

    with ProcessPoolExecutor(max_workers=6) as pool:
        ikb = {}
        bl = sorted(blocks)
        for i in range(0, len(bl), 2000):
            for s, f, sk in pool.submit(_ik_worker, bl[i:i + 2000]).result():
                ikb[s] = (f, sk)
        ikp = {}
        pl = sorted(prod)
        for i in range(0, len(pl), 2000):
            for s, f, sk in pool.submit(_ik_worker, pl[i:i + 2000]).result():
                ikp[s] = (f, sk)

    full_b = {v[0] for v in ikb.values() if v[0]}
    full_p = {v[0] for v in ikp.values() if v[0]}
    skel_b = {v[1] for v in ikb.values() if v[1]}
    skel_p = {v[1] for v in ikp.values() if v[1]}
    print()
    print("① 身份层面复核")
    print(f"   砌块 {len(blocks):,}   产物 {len(prod):,}")
    print(f"   full InChIKey 交集 = {len(full_b & full_p)}   <-- 同分子才算真重叠")
    print(f"   骨架(skel) 交集    = {len(skel_b & skel_p)}   <-- 含立体异构")
    print(f"   骨架撞但整分子不撞 = {len((skel_b & skel_p) - full_b)}  <-- 立体异构造成")

    skel2b, skel2p = {}, {}
    for s, (f, sk) in ikb.items():
        skel2b.setdefault(sk, []).append((s, f))
    for s, (f, sk) in ikp.items():
        skel2p.setdefault(sk, []).append((s, f))
    print()
    print("   骨架撞的例子:")
    for n, sk in enumerate(sorted(skel_b & skel_p)):
        if n >= 8:
            break
        print(f"     skel {sk}")
        for s, f in skel2b[sk][:2]:
            print(f"        砌块 {s[:68]:<68} {f}")
        for s, f in skel2p[sk][:2]:
            print(f"        产物 {s[:68]:<68} {f}")

    print()
    print("② 数据质量：同一反应【两侧出现同一分子】")
    same, n_rx = 0, 0
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
        n_rx += 1
        sp = split_cx(cx)
        if sp is None:
            continue
        lhs, _mid, rhs = sp

        def keys(seg):
            out = set()
            for p in seg.split("."):
                p = p.strip()
                if not p:
                    continue
                g = canon_key(p)
                if g:
                    out.add(g[0])
            return out
        if keys(lhs) & keys(rhs):
            same += 1
    print(f"   两侧含同一分子的反应 = {same:,} / {n_rx:,} ({same/max(n_rx,1)*100:.2f}%)")
    print("   -> 这类反应里该分子同时进 R 和 P，因此【不会】被误判成砌块")


if __name__ == "__main__":
    main()
