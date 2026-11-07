# -*- coding: utf-8 -*-
"""一次性探针：相似度检索的耗时到底花在哪（一个脚本只回答一个问题）。"""
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
    from rdkit import Chem, DataStructs, RDLogger
    RDLogger.DisableLog("rdApp.*")
    inv = qb.load_inventory()
    smis = [e["smiles"] for e in inv.index().values()]
    print(f"分子 {len(smis)} 个（平均重原子 "
          f"{sum(len(Chem.MolFromSmiles(s).GetAtoms()) for s in smis[:50])//50}）")

    t0 = time.time()
    mols = [Chem.MolFromSmiles(s) for s in smis]
    print(f"① MolFromSmiles 全量: {time.time()-t0:.2f}s")

    t0 = time.time()
    fps = [Chem.RDKFingerprint(m, fpSize=2048) for m in mols]
    print(f"② RDKFingerprint(fpSize) 全量: {time.time()-t0:.2f}s")

    t0 = time.time()
    fps2 = [Chem.RDKFingerprint(m) for m in mols]
    print(f"③ RDKFingerprint(默认 2048?) 全量: {time.time()-t0:.2f}s"
          f"  nbits={fps2[0].GetNumBits()}")

    t0 = time.time()
    hexes = [DataStructs.BitVectToFPSText(f) for f in fps]
    print(f"④ ToFPSText 全量: {time.time()-t0:.2f}s")

    t0 = time.time()
    back = [DataStructs.CreateFromFPSText(h) for h in hexes]
    print(f"⑤ CreateFromFPSText 全量: {time.time()-t0:.2f}s")

    q = fps[0]
    t0 = time.time()
    for f in fps:
        DataStructs.TanimotoSimilarity(q, f)
    print(f"⑥ 552 次 TanimotoSimilarity(逐次调用): {time.time()-t0:.3f}s")

    t0 = time.time()
    sims = DataStructs.BulkTanimotoSimilarity(q, fps)
    print(f"⑦ BulkTanimotoSimilarity 全量: {time.time()-t0:.3f}s")

    # 新版 Morgan 生成器（如果 RDKit 有）
    try:
        from rdkit.Chem import rdFingerprintGenerator
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        t0 = time.time()
        mfps = [gen.GetFingerprint(m) for m in mols]
        print(f"⑧ MorganGenerator 全量: {time.time()-t0:.2f}s")
        t0 = time.time()
        _ = DataStructs.BulkTanimotoSimilarity(mfps[0], mfps)
        print(f"⑨ Bulk(MorganGenerator) 全量: {time.time()-t0:.3f}s")
    except Exception as ex:                      # noqa: BLE001
        print(f"⑧ MorganGenerator 不可用: {type(ex).__name__}: {ex}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
