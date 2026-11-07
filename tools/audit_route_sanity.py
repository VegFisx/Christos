# -*- coding: utf-8 -*-
r"""抽查：B 之后的路线里，有多少是"结构合法但化学荒谬"的？

动机：B 之后可用率 26% -> 42%，但同时形式成功率 45% -> 82%。
      抽查里出现这种路线：
        目标 CSc1ncc(C(=O)O)c(NC2(c3ccccc3)CC2)n1
        <- O=C([O-])[O-]（碳酸根） + 目标换掉一个基团
        再拆碳酸根 -> 碳酸氢根 -> 碳酸
      每步"结构上"都合法（前体比目标小），但用碳酸盐当合成原料是荒谬的。

本脚本量三件事（都不改判据，只统计）：
  A. 路线里是否含"极端小分子/无机碳"前体（CO2/H2CO3/HCO3-/CO3^2-/甲酸/甲酸盐/尿素…）
  B. 路线步数分布
  C. "残基那一步"是否仍大量存在（B 只在递归时避开，一步到位仍可能命中）

用法: python audit_route_sanity.py [目标数]
输出 reports/route_sanity.json
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
OUT = STAGE / "reports" / "route_sanity.json"

# 极端小分子 / 无机碳：当原料用就是荒谬（不是不能买，是没人这么合成）
ABSURD = {"O=C=O", "O=C(O)O", "O=C([O-])O", "O=C([O-])[O-]", "O=CO", "O=C[O-]",
          "N", "O", "O=O", "C", "CO", "CC", "CCl", "Cl", "Br", "I", "S", "N#N",
          "O=C(N)N", "NC=O", "O=CN=O"}


def hac(smi):
    m = Chem.MolFromSmiles(smi)
    return m.GetNumHeavyAtoms() if m else -1


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    beam = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    t0 = time.time()
    print("=" * 92)
    print(f"路线荒谬性抽查（depth={depth} beam={beam}）")
    print("=" * 92)

    tg = sample_targets(n)
    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    eng = RetroSearch(load_rdchiral_templates(), av, blocks_full=bf, blocks_skel=bs,
                      filter_weird=True, weird_charged=True, skel_tol=1)
    stat = Counter()
    examples = []
    for i, t in enumerate(tg, 1):
        routes, _s = eng.search(t, max_depth=depth, beam=beam, max_routes=3)
        for r in routes:
            stat["路线数"] += 1
            has_absurd = False
            max_inert = 0
            for st in r.steps:
                for p in st.precursors:
                    if p in ABSURD:
                        has_absurd = True
                        max_inert = max(max_inert, hac(p))
            if has_absurd:
                stat["含极端小分子/无机碳"] += 1
                if len(examples) < 8:
                    examples.append({"target": t,
                                     "steps": [{"t": s.target, "p": list(s.precursors)}
                                               for s in r.steps][:3]})
            stat[f"步数_{len(r.steps)}"] += 1
        if i % 20 == 0:
            print(f"   {i}/{len(tg)}  路线 {stat['路线数']}  "
                  f"荒谬 {stat['含极端小分子/无机碳']}  ({time.time()-t0:.0f}s)", flush=True)

    print()
    print("=" * 92)
    print("结果")
    print("=" * 92)
    tr = stat["路线数"]
    print(f"  路线总数 {tr}")
    print(f"  ├ 含极端小分子/无机碳（荒谬）  {stat['含极端小分子/无机碳']:>4}"
          f"  ({stat['含极端小分子/无机碳']/max(tr,1)*100:5.1f}%)")
    print(f"  └ 其余                        {tr-stat['含极端小分子/无机碳']:>4}"
          f"  ({(tr-stat['含极端小分子/无机碳'])/max(tr,1)*100:5.1f}%)")
    print()
    print("  步数分布:", {k: v for k, v in sorted(stat.items()) if k.startswith("步数_")})
    print()
    print("  荒谬路线例子（前 4）:")
    for e in examples[:4]:
        print(f"     目标 {e['target'][:56]}")
        for s in e["steps"]:
            print(f"        {s['t'][:42]:<42} <- {str(s['p'])[:64]}")

    OUT.write_text(json.dumps({"n_targets": len(tg), "stat": dict(stat),
                               "examples": examples,
                               "elapsed_sec": round(time.time() - t0, 1)},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
