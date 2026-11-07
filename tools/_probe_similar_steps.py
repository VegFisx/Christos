# -*- coding: utf-8 -*-
"""一次性计时：query_similar 的每一步各花多少时间（只回答这一个问题）。"""
from __future__ import annotations

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

import query_base as qb  # noqa: E402


def main() -> int:
    from rdkit import DataStructs
    inv = qb.load_inventory()
    ref = "glycyrrhizin"

    t = time.perf_counter()
    ident = qb.resolve_molecule(ref)
    print(f"① resolve_molecule        {time.perf_counter()-t:6.2f}s  kind={ident['kind']} "
          f"cands={len(ident.get('candidates', []))}")
    q_smiles = ident.get("smiles") or qb.canon((ident["candidates"][0]["smiles"]
                                                if ident.get("candidates") else ""))

    t = time.perf_counter()
    q_fp = qb.fp_of_smiles(q_smiles)
    print(f"② 查询分子指纹            {time.perf_counter()-t:6.2f}s")

    t = time.perf_counter()
    _f, fp_map, st = qb.build_fingerprints(inv)
    print(f"③ build_fingerprints      {time.perf_counter()-t:6.2f}s  {st}")

    pairs = [(e['smiles'], fp_map[e['smiles']]) for e in inv.index().values()
             if e['smiles'] in fp_map]
    t = time.perf_counter()
    bvs = [qb._store_to_bv(h) for _s, h in pairs]
    print(f"④ 解出 {len(bvs)} 个位向量     {time.perf_counter()-t:6.2f}s")

    t = time.perf_counter()
    q_bv = qb._store_to_bv(q_fp)
    sims = DataStructs.BulkTanimotoSimilarity(q_bv, bvs)
    print(f"⑤ BulkTanimotoSimilarity  {time.perf_counter()-t:6.2f}s")

    hit = [(s, x) for (s, _h), x in zip(pairs, sims) if x >= 0.35]
    print(f"   命中 {len(hit)} 个")

    t = time.perf_counter()
    idx = inv.index()
    s2k = inv.by_smiles()
    for s, _x in hit[:50]:
        e = idx[s2k[s]]
        _rounds = [p["round"] for src in e["sources"].values() for p in src["paths"]]
    print(f"⑥ 前 50 个命中组行        {time.perf_counter()-t:6.2f}s")

    t = time.perf_counter()
    for s, _x in hit[:50]:
        e = idx[s2k[s]]
        _ = [qb.label_of(src["source_smiles"], qb.seed_label_map(inv.spec))
             for src in list(e["sources"].values())[:4]]
    print(f"⑦ 前 50 行 label_of       {time.perf_counter()-t:6.2f}s")

    t = time.perf_counter()
    for s, _x in hit[:50]:
        e = idx[s2k[s]]
        _ = qb.names_of_inchikey(e["inchikey"], limit=1) if e["inchikey"] else []
    print(f"⑧ 前 50 行 names_of_ik    {time.perf_counter()-t:6.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
