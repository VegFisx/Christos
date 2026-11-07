# -*- coding: utf-8 -*-
r"""一次性验收：真实规模跑「底座 + A/B/C 三入口」，只打印摘要（不落额外文件）。

用法: & $py -u tools\_verify_query_entries.py
"""
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

import query_base as qb                                   # noqa: E402

BOUND = ("边界：查不到 ≠ 不存在（= 当前模板库 + 当前轮数没枚举出来）；"
         "B 单分子只有单底物化学；新产物没有名字")


def main() -> int:
    t0 = time.time()
    print("=" * 100)
    print("真实规模验收：甘草全成分 · 煎煮 · 1 轮")
    print("=" * 100)
    from herb import compounds_of_herb
    comps = compounds_of_herb("甘草", limit=12)
    seeds = [(c.name, c.smiles, "tcm.db") for c in comps]
    print(f"  取到成分 {len(seeds)} 个（{time.time()-t0:.1f}s）")

    spec = qb.RunSpec(seeds=seeds, cond_name="煎煮", rounds=1)
    inv = qb.build_inventory(spec, score=True)
    st = inv.stats
    print(f"  产物 {st.n_products} 个 · 出处路径 {st.n_paths_kept} 条 · 耗时 {st.seconds}s")
    print(f"  InChIKey 成功 {st.ik_ok}（缓存 {st.ik_cached}）· 失败 {st.ik_fail}")
    print(f"  剔掉的「产物==输入」{st.n_self_products} 条 · 逐轮 {st.per_round_new}")
    pf, xf = qb.dump_inventory(inv)
    print(f"  台账 -> {pf}")
    print(f"  索引 -> {xf}")

    # ---- 入口 C：全量 + 子结构 + 名称 ----
    print()
    print("-" * 100)
    print("入口 C 检索")
    r_all = qb.query_inventory(inv, limit=3)
    print(f"  [C 无过滤] {r_all['n_hits']} 个产物")
    for h in r_all["hits"]:
        print(f"     r{h['min_round']} {h['formula']:<18} {str(h['rules'])[:40]:<42} {h['smiles'][:40]}")
    r_sub = qb.query_inventory(inv, substructure="c1ccccc1", limit=3)
    print(f"  [C 子结构=苯环] 命中 {r_sub['n_hits']} 个")
    r_gly = qb.query_inventory(inv, name="glycyrrh", limit=5)
    print(f"  [C 名称=glycyrrh（英文，库里有）] 命中 {r_gly['n_hits']} 个"
          f"（库内候选 {len(r_gly.get('name_candidates', []))} 个）")

    # ---- 入口 A：真产物 / 库里有的分子 / 肯定不在的分子 ----
    print()
    print("-" * 100)
    print("入口 A 查产物")
    keys = list(inv.index().keys())
    if keys:
        e = inv.index()[keys[0]]
        rA = qb.query_product(inv, e["smiles"])
        h = rA["hits"][0] if rA["found"] else {}
        print(f"  [A 真产物] found={rA['found']} 轮次={h.get('min_round')} "
              f"路径={h.get('n_paths')} 来源分子={h.get('n_sources')} "
              f"规则={str(h.get('rules'))[:60]}")
    seed_labels = qb.seed_label_map(inv.spec)
    if keys:
        e0 = inv.index()[keys[0]]
        s0 = list(e0["sources"].values())[0]
        print(f"  [新] 来源分子可读名 label_of -> "
              f"{qb.label_of(s0['source_smiles'], seed_labels)!r}"
              f"（角色 {s0.get('role')}）")
        print(f"  [新] 方向信号 reversible={e0['reversible']} "
              f"co_products={len(e0['co_products'])} 个")
    rA = qb.query_product(inv, e["smiles"])
    if rA["found"]:
        h0 = rA["hits"][0]
        print(f"  [新] 入口 A 输出：source_label="
              f"{h0['sources'][0].get('source_label')!r} "
              f"role={h0['sources'][0].get('role')!r} "
              f"reversible={h0['reversible']} co={len(h0['co_products'])}")
    rA2 = qb.query_product(inv, "OC(=O)C(F)(F)F")
    print(f"  [A 三氟乙酸（不该有）] found={rA2['found']}")
    rA3 = qb.query_product(inv, "glycyrrhizin")
    print(f"  [A 名称 glycyrrhizin] kind={rA3['resolved']['kind']} found={rA3['found']} "
          f"候选={len(rA3['resolved'].get('candidates', []))}")

    # ---- 入口 B：单分子 / 双分子 ----
    print()
    print("-" * 100)
    print("入口 B 查底物")
    rB1 = qb.query_substrate("OCc1ccccc1", cond_name="煎煮", max_products=5)
    print(f"  [B 单分子 苯甲醇] 产物 {rB1['n_products']} 个 · 规则 "
          f"{sorted({p['rule_name'] for p in rB1['products']})}")
    rB2 = qb.query_substrate_pair("OCc1ccccc1", "NCCc1ccc(O)cc1", cond_name="煎煮",
                                  max_products=5)
    print(f"  [B 双分子 苯甲醇+酪胺] 产物 {rB2['n_products']} 个")

    print()
    print(f"  ⚠ {BOUND}")
    print(f"  总耗时 {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
