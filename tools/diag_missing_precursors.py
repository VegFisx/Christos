# -*- coding: utf-8 -*-
r"""①诊断：端到端搜索失败的目标，到底"缺"什么？

用 depth=3 beam=4（当前默认）跑 100 个目标，对【失败的】目标逐个记录：
  A. 有多少切断方案是"只差一个前体不可得"
  B. 那些"不可得前体"都是什么（分子式/大小/是否出现在更宽的集合里）
  C. 这些不可得前体出现在哪些集合里（旧终端 / 砌块full / 砌块骨架 / 全砌块含试剂 / 都不在）
       -> 直接回答"补终止集合能不能解决"
输出 reports/diag_missing_precursors.json

用法: python diag_missing_precursors.py [目标数] [深度]
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
for _p in (STAGE / "tools", STAGE / "libs", Path(r"D:\TCMAI\src")):
    sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from retro_search import (RetroSearch, load_available, load_purchasable_blocks,  # noqa: E402
                          load_rdchiral_templates, ik, canon)
from bench_new_templates import sample_targets  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "diag_missing_precursors.json"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    beam = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    t0 = time.time()
    print("=" * 92)
    print(f"①诊断：失败的端到端目标缺什么（depth={depth} beam={beam}）")
    print("=" * 92)

    tg = sample_targets(n)
    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    bf_all, bs_all = load_purchasable_blocks(True)      # 含试剂（更宽的砌块集合）
    tmpl = load_rdchiral_templates()
    eng = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                      filter_weird=True, weird_charged=True, skel_tol=1)
    # 更宽判定的引擎（砌块含试剂）
    eng_wide = RetroSearch(tmpl, av, blocks_full=bf_all, blocks_skel=bs_all,
                           filter_weird=True, weird_charged=True, skel_tol=1)
    print(f"模板 {len(tmpl):,}；终端 旧{len(av):,} + 砌块{len(bf):,}（宽版 {len(bf_all):,}）")

    fails = []
    ok_n = 0
    miss_stat = Counter()
    ghost_hist = Counter()       # 每个失败目标"只差几个前体"的分布
    missing_detail = []
    for i, t in enumerate(tg, 1):
        routes, _stat = eng.search(t, max_depth=depth, beam=beam)
        if routes:
            ok_n += 1
            continue
        # 失败 -> 分析
        dis = eng.disconnections(t)
        best_gap = None
        for st in dis:
            avs = [eng.is_available(p) for p in st.precursors]
            gap = sum(1 for a in avs if not a)
            if best_gap is None or gap < best_gap:
                best_gap = gap
        if best_gap is not None:
            ghost_hist[best_gap] += 1
        fails.append(t)
        if i % 20 == 0:
            print(f"   {i}/{len(tg)}  成功 {ok_n}  失败 {len(fails)}  ({time.time()-t0:.0f}s)",
                  flush=True)

    print(f"\n成功 {ok_n}/{len(tg)}，失败 {len(fails)}")
    print(f"失败目标的『最少缺几个前体』分布: {dict(sorted(ghost_hist.items()))}")

    # 对失败目标：把所有"接近可行"的方案里不可得的前体收集起来
    print("\n分析失败目标的不可得前体...", flush=True)
    hashes = Counter()          # 不可得前体的 canonical smiles
    for t in fails:
        dis = eng.disconnections(t)
        for st in dis[:60]:
            avs = [eng.is_available(p) for p in st.precursors]
            for p, a in zip(st.precursors, avs):
                if not a:
                    cp = canon(p)
                    if cp:
                        hashes[cp] += 1
    print(f"   共 {len(hashes):,} 个不同的不可得前体（{sum(hashes.values()):,} 次出现）")

    # 这些前体在【更宽】的集合里能找到吗？
    recover = Counter()
    detail = []
    for cp, cnt in hashes.most_common(400):
        w = eng_wide.is_available(cp)
        m = Chem.MolFromSmiles(cp)
        hac = m.GetNumHeavyAtoms() if m else -1
        mw = Descriptors.MolWt(m) if m else -1
        f = rdMolDescriptors.CalcMolFormula(m) if m else "?"
        if w:
            recover["落在【砌块含试剂】宽集合里"] += 1
        else:
            recover["还是不在任何集合里"] += 1
        recover[f"重原子数{'<=8' if hac<=8 else ('9-15' if hac<=15 else ('16-25' if hac<=25 else '>25'))}"] += 1
        detail.append({"smiles": cp, "count": cnt, "heavy_atoms": hac,
                       "MW": round(mw, 1), "formula": f,
                       "in_wide_set": bool(w), "wide_tag": w or ""})

    print("\n不可得前体的构成（前 400 个高频）:")
    for k, v in recover.most_common():
        print(f"   {k:<28} {v}")

    print("\n例子（前 12，看它们像不像「能买到的」）:")
    for d in detail[:12]:
        tag = d["wide_tag"] or "不在任何集合"
        print(f"   x{d['count']:<3} {d['formula']:<16} MW{d['MW']:7.1f} 重{d['heavy_atoms']:<3} "
              f"{tag[:22]:<22} {d['smiles'][:52]}")

    OUT.write_text(json.dumps({
        "n_targets": n, "depth": depth, "beam": beam,
        "success": ok_n, "fail": len(fails),
        "gap_hist": {str(k): v for k, v in sorted(ghost_hist.items())},
        "n_missing_unique": len(hashes),
        "recover": dict(recover),
        "detail_top400": detail,
        "elapsed_sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
