# -*- coding: utf-8 -*-
r"""新搜索器：新模板库 + 多步回溯，看端到端能到多少。

口径：
  模板   = 新的 3,025 条聚类逆模板（与 bench_new_templates 相同加载方式）
  终止集合 = 旧(COCONUT+tcm.db) + ①砌块
  搜索   = 深度受限的束搜索：
           ① 先看有没有"全部前体可得"的方案 -> 直接成路
           ② 否则挑【最不可得的前体】递归拆（优先拆最大的）
           ③ 每层限制候选数，避免爆炸
  成功   = 能找到一条深度<=D 的完整路线
输出 reports/bench_multistep.json

用法: python bench_multistep.py [目标数] [最大深度] [beam]
"""
import json
import os
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
from rdkit.Chem import Descriptors  # noqa: E402
from retro_search import (RetroSearch, load_available, load_purchasable_blocks)  # noqa: E402
from bench_new_templates import load_new_templates, sample_targets  # noqa: E402
from retro_search import load_retro_templates  # noqa: E402

RDLogger.DisableLog("rdApp.*")
_TAG = os.environ.get("CHEMCREACT_MS_TAG", "v0")
OUT = STAGE / "reports" / ("bench_multistep__%s.json" % _TAG)
CLUSTERED = STAGE / "reports" / "retro_templates_clustered.jsonl"


def search(eng, target, max_depth=2, beam=4, max_dis=400,
           max_time_s=60.0):
    """返回 (成功?, 路线, 统计)。束搜索 + 时间上限。"""
    stat = Counter()
    t0 = time.time()
    node_budget = [3000]

    def expand(mol, path, depth):
        if time.time() - t0 > max_time_s:
            stat["超时"] += 1
            return None
        if node_budget[0] <= 0:
            return None
        node_budget[0] -= 1
        dis = eng.disconnections(mol)
        stat[f"深度{depth}_方案数"] += len(dis)
        if not dis:
            return None
        # 打分：全部前体可得的方案优先
        scored = []
        for st in dis[:max_dis]:
            avs = [eng.is_available(p) for p in st.precursors]
            n_av = sum(1 for a in avs if a)
            scored.append((n_av == len(st.precursors), n_av, st, avs))
        scored.sort(key=lambda x: (not x[0], -x[1]))
        for full, n_av, st, avs in scored[:beam]:
            if full:
                stat["一步到位"] += 1
                return path + [st]
        if depth >= max_depth:
            return None
        # 递归：挑最不可得的前体里最大的那个
        cands = []
        for full, n_av, st, avs in scored[:beam * 8]:
            un = [p for p in st.precursors if not eng.is_available(p)]
            if not un:
                continue
            un.sort(key=lambda s: -Descriptors.MolWt(Chem.MolFromSmiles(s)))
            cands.append((un[0], st))
        seen = set()
        picked = []
        for mol2, st in cands:
            if mol2 in seen:
                continue
            seen.add(mol2)
            picked.append((mol2, st))
            if len(picked) >= beam:
                break
        stat[f"深度{depth}_递归"] += len(picked)
        for mol2, st in picked:
            r = expand(mol2, path + [st], depth + 1)
            if r is not None:
                return r
        return None

    route = expand(target, [], 1)
    return route is not None, route, stat


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    beam = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    t0 = time.time()
    print("=" * 92)
    print(f"新搜索器：新模板库 + 多步回溯（depth<={max_depth}, beam={beam}）")
    print("=" * 92)

    tg = sample_targets(n)
    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    if "--use-lib" in sys.argv:
        from retro_search import load_rdchiral_templates
        new = load_rdchiral_templates(os.environ.get("CHEMCREACT_MS_TPL") or None)
        bad = multi = 0
    else:
        new, bad, multi = load_new_templates(CLUSTERED)
    use_old = "--with-old" in sys.argv
    if use_old:
        old = load_retro_templates()
        new = new + old
        print(f"模板 {len(new):,} 条 = 新 {len(new)-len(old):,} + 旧 {len(old):,}（合并模式）")
    else:
        print(f"模板 {len(new):,} 条（仅新库）")
    print(f"终止集合 旧 {len(av):,} + 砌块 {len(bf):,}")
    eng = RetroSearch(new, av, blocks_full=bf, blocks_skel=bs,
                      filter_weird=True, weird_charged=True, skel_tol=1)

    use_lib = "--use-lib" in sys.argv     # 用 retro_search.RetroSearch.search（收尾后的默认路径）
    ok = 0
    depth_hist = Counter()
    per = []
    for i, t in enumerate(tg, 1):
        n_routes = n_usable = None
        if use_lib:
            heur = 3 if "--heuristic3" in sys.argv else (
                2 if "--heuristic2" in sys.argv else 1)
            routes, stat = eng.search(t, max_depth=max_depth, beam=beam,
                                      heuristic=heur)
            ok_i = bool(routes)
            route = routes[0].steps if routes else None
            n_routes = len(routes)
            n_usable = sum(1 for rt0 in routes if getattr(rt0, "usable", True))
            stat = dict(stat)
        else:
            ok_i, route, stat = search(eng, t, max_depth=max_depth, beam=beam)
        if ok_i:
            ok += 1
            depth_hist[len(route)] += 1
        per.append({"target": t, "ok": ok_i,
                    "depth": (len(route) if ok_i else None),
                    "n_routes": (n_routes if use_lib else None),
                    "n_usable": (n_usable if use_lib else None),
                    "stat": dict(stat)})
        if i % 10 == 0:
            el = time.time() - t0
            print(f"   {i}/{len(tg)}  成功 {ok} ({ok/i*100:.1f}%)  {el:.0f}s  "
                  f"预计还需 {el/i*(len(tg)-i):.0f}s", flush=True)

    print()
    print("=" * 92)
    print(f"★ 端到端成功率（深度<={max_depth}, beam={beam}）= {ok}/{len(tg)}"
          f" = {ok/len(tg)*100:.1f}%")
    print(f"   路线步数分布: {dict(depth_hist)}")
    print("=" * 92)
    OUT.write_text(json.dumps({
        "n_targets": len(tg), "max_depth": max_depth, "beam": beam,
        "n_templates": len(new), "success": ok,
        "rate": round(ok / len(tg), 4),
        "depth_hist": dict(depth_hist),
        "elapsed_sec": round(time.time() - t0, 1),
        "targets": per,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
