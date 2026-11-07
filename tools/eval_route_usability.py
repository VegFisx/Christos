# -*- coding: utf-8 -*-
r"""① 路线化学可用率评测（judgement v2）★ 判据修正版 ★

v1 的教训（实测）：v1 用"前体重原子数之和 >= 目标"判"无进展"，
把 6 条【已知化学合法】的路线全误杀了 —— 因为缩合/取代反应本来就会
让前体原子数之和超过目标（例：沙洛酚 <- 酪胺 + 水杨酸，酰胺偶联脱一分子水）。
-> 判据必须换成【结构层面】的：这个前体是不是"目标本身换个基团"。

v2 判据（每条路线逐步骤）
--------------------------------------------------------------------
R1 残基路线 : 某前体【包含目标的完整骨架】（前体 >= 目标 重原子数 且 目标是其子结构）
              -> "把目标换个基团再变回来"，不是拆解。典型：氨基版目标、溴代版目标
R2 前体更大 : 某前体重原子数 > 目标重原子数
R3 惰性小分子: 目标 >15 重原子 且 有前体重原子数 <= 2（CCl/CC/CO/水）
判据：(路线可用) = 所有步骤都不触发 R1~R3

用法: python eval_route_usability.py [目标数] [深度] [beam] [每题路线数]
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
from retro_search import (RetroSearch, load_available, load_purchasable_blocks,  # noqa: E402
                          load_rdchiral_templates)
from bench_new_templates import sample_targets  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "route_usability.json"

# ★ 判据统一：直接复用 retro_search.step_usability ★
#   （以前这里自己实现了一份 judge_step，与搜索排序用的判据是"两套口径"，
#     加 R4 时才发现不一致的隐患 —— 一律改为单一来源）
from retro_search import step_usability  # noqa: E402


def hac(mol):
    return mol.GetNumHeavyAtoms() if mol else -1


def judge_step(step):
    """返回触发的规则列表（空 = 这步干净）。判据来自 retro_search.step_usability。"""
    ok, why = step_usability(step.target, step.precursors)
    return [] if ok else [why]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    beam = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    max_routes = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    t0 = time.time()
    print("=" * 92)
    print(f"① 路线化学可用率 v2（depth={depth} beam={beam} max_routes={max_routes}）")
    print("=" * 92)

    tg = sample_targets(n)
    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    tmpl = load_rdchiral_templates()
    eng = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                      filter_weird=True, weird_charged=True, skel_tol=1)
    print(f"模板 {len(tmpl):,}；终端 旧{len(av):,} + 砌块{len(bf):,}")

    goal_ok = goal_usable_any = goal_usable_first = 0
    n_routes = route_ok = 0
    rule_hits = Counter()
    bad_examples = []
    for i, t in enumerate(tg, 1):
        routes, _st = eng.search(t, max_depth=depth, beam=beam, max_routes=max_routes)
        if not routes:
            continue
        goal_ok += 1
        any_ok = False
        for ri, r in enumerate(routes):
            n_routes += 1
            bad = []
            for st in r.steps:
                bad += judge_step(st)
            if bad:
                for b in bad:
                    rule_hits[b] += 1
                if len(bad_examples) < 10:
                    bad_examples.append({
                        "target": t, "route_idx": ri + 1,
                        "steps": [{"t": s.target, "p": list(s.precursors)} for s in r.steps],
                        "rules": sorted(set(bad))})
            else:
                route_ok += 1
                any_ok = True
                if ri == 0:
                    goal_usable_first += 1
        if any_ok:
            goal_usable_any += 1
        if i % 20 == 0:
            print(f"   {i}/{len(tg)}  有路线 {goal_ok}  路线 {n_routes}  可用 {route_ok}  "
                  f"({time.time()-t0:.0f}s)", flush=True)

    print()
    print("=" * 92)
    print("结果")
    print("=" * 92)
    print(f"  目标 {len(tg)}")
    print(f"  ├ 找到路线（形式成功）      {goal_ok:>4}  ({goal_ok/len(tg)*100:5.1f}%)")
    print(f"  ├ 至少一条可用路线          {goal_usable_any:>4}  "
          f"({goal_usable_any/len(tg)*100:5.1f}%)  <- ★ 可用率")
    print(f"  └ 第一条路线就可用          {goal_usable_first:>4}  "
          f"({goal_usable_first/len(tg)*100:5.1f}%)  <- 用户看到的第一条")
    print(f"  路线总数 {n_routes}，可用 {route_ok} ({route_ok/max(n_routes,1)*100:.1f}%)")
    print()
    print("  规则命中（一条路线可触发多条）:")
    for k, v in rule_hits.most_common():
        print(f"     {k:<16} {v}")
    print()
    print("  坏路线例子（前 5）:")
    for e in bad_examples[:5]:
        print(f"     目标 {e['target'][:56]}")
        for s in e["steps"]:
            print(f"        {s['t'][:44]:<44} <- {str(s['p'])[:68]}")
        print(f"        规则 {e['rules']}")

    OUT.write_text(json.dumps({
        "criteria_version": 2,
        "n_targets": len(tg), "depth": depth, "beam": beam, "max_routes": max_routes,
        "goal_with_routes": goal_ok,
        "goal_usable_any": goal_usable_any,
        "goal_usable_first": goal_usable_first,
        "formal_rate": round(goal_ok / len(tg), 4),
        "usable_rate": round(goal_usable_any / len(tg), 4),
        "first_route_usable_rate": round(goal_usable_first / len(tg), 4),
        "n_routes": n_routes, "n_routes_usable": route_ok,
        "rule_hits": dict(rule_hits), "bad_examples": bad_examples,
        "elapsed_sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
