# -*- coding: utf-8 -*-
"""测「coverage 产物 + 有界立体枚举」的召回与候选代价（只在 miss 上算）。

口径：
  · 只对 coverage 产物做立体扩展；模板含 '@' 的不动（立体已指定）。
  · 产物先 RemoveStereochemistry，再枚举立体异构体（上限 cap），并显式加入平面版。
  · 中心数 > max_centers 的产物只加平面版，不枚举（控制组合爆炸）。
  · 召回 = 文献主产物在扩展后的候选集里；代价 = 扩展后候选数 - 原 coverage 候选数。

策略一次跑完：cap4_c2 / cap8_c3 / cap16_c3 / cap8_c4。
"""
from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "core", ROOT / "libs", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem.EnumerateStereoisomers import (  # noqa: E402
    EnumerateStereoisomers, StereoEnumerationOptions)
from rescue import RescuePool  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import probe_uspto_train_coverage as P  # noqa: E402

POLICIES = [("cap4_c2", 4, 2), ("cap8_c3", 8, 3),
            ("cap16_c3", 16, 3), ("cap8_c4", 8, 4)]


def variants_of(smi: str, cap: int, max_centers: int) -> set:
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return set()
    flat = Chem.Mol(m)
    Chem.RemoveStereochemistry(flat)
    flat_smi = Chem.MolToSmiles(flat)
    n_c = len(Chem.FindMolChiralCenters(flat, includeUnassigned=True,
                                        useLegacyImplementation=False))
    out = {flat_smi}
    if n_c == 0 or n_c > max_centers:
        return out
    opts = StereoEnumerationOptions(maxIsomers=cap, onlyUnassigned=False,
                                    unique=True, tryEmbedding=False)
    try:
        for x in EnumerateStereoisomers(flat, options=opts):
            out.add(Chem.MolToSmiles(x))
            if len(out) >= cap + 1:
                break
    except Exception:
        pass
    return out


def main() -> int:
    rows = P.load_rows()
    miss = sorted(P.load_miss())
    pool = RescuePool(path=P.TPL, min_support=1, max_support=10 ** 9, verbose=False)
    print("miss %d；模板池 %d" % (len(miss), len(pool.tpls)), flush=True)

    stats = {name: {"hits": 0, "extra": 0, "n": 0, "per": Counter()}
             for name, _c, _m in POLICIES}
    base_hits = 0
    t0 = time.time()
    for k, i in enumerate(miss):
        rec = rows.get(i)
        if not rec:
            continue
        mols = [Chem.MolFromSmiles(s) for s in rec["reactants"]]
        mols = [m for m in mols if m is not None]
        if not mols:
            continue
        jobs = [(m,) for m in mols]
        if len(mols) == 2:
            jobs.append((mols[0], mols[1]))
        got = []
        for job in jobs:
            got.extend(pool.run(list(job)))
        # 去重（产物, 模板），保留每个产物一个模板做立体判断
        base = {}
        for smi, tpl, _sup in got:
            cs = P.canon(smi)
            if cs and cs not in base:
                base[cs] = tpl
        want = P.canon(rec["product"])
        if want in base:
            base_hits += 1
        for name, cap, mc in POLICIES:
            ext = set(base)
            for smi, tpl in base.items():
                if "@" in (tpl or ""):
                    continue
                ext |= variants_of(smi, cap, mc)
            st = stats[name]
            st["n"] += 1
            st["extra"] += max(0, len(ext) - len(base))
            st["per"][len(ext) - len(base)] += 1
            if want and want in ext:
                st["hits"] += 1
        if (k + 1) % 50 == 0:
            print("  ...%d/%d  %.0fs" % (k + 1, len(miss), time.time() - t0), flush=True)

    n = len(miss)
    print("\nbase coverage 精确命中 %d/%d" % (base_hits, n))
    for name, cap, mc in POLICIES:
        st = stats[name]
        add = st["hits"] - base_hits
        print("%-8s cap=%-2d 中心<=%d : 命中 %d (%+.0f) · 每条miss新增候选 %.1f"
              " · 增量分布 %s"
              % (name, cap, mc, st["hits"], add,
                 st["extra"] / max(1, st["n"]),
                 dict(sorted(st["per"].items())[:8])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
