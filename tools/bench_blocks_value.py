# -*- coding: utf-8 -*-
r"""受控评估：把①可购砌块并进终止集合，逆合成到底变好了多少？

口径（先说清再测）
--------------------------------------------------------------------
目标分子 : ORD 真实反应的【产物】（天然产物之外的普通药物化学分子），
           分子量 <= 500，抽样 N 个（固定随机种子）
切断方案 : 9,770 条反转模板，与 retro_search 完全同一套
两组对照 : A = 旧终止集合（COCONUT + tcm.db，277,268）
           B = 旧 + ①砌块（32,341）
指标     : 一步到位率（所有前体都是终点）/ 未命中率 / 平均终点命中数
           以及"B 比 A 多解决的分子数"
为什么这样测：切断方案与两组无关 -> 只算一次，两组共用，避免重复计算

输出 reports\bench_blocks_value.json

用法: python bench_blocks_value.py [目标数]
"""
import json
import random
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
sys.path.insert(0, str(STAGE / "tools"))
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

import duckdb  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors  # noqa: E402
from build_purchasable_blocks import BIG, split_cx, canon_key  # noqa: E402
from retro_search import (RetroSearch, load_available, load_retro_templates,  # noqa: E402
                          load_purchasable_blocks, ik, canon)
from ord_schema.proto import reaction_pb2  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "bench_blocks_value.json"


def sample_targets(n, offset=200000):
    """从 ORD 抽 N 个 '像药' 的产物分子（MW<=500，单组分，非盐）。"""
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') OFFSET {offset} LIMIT 40000"
    ).fetchall()
    out, seen = [], set()
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
        sp = split_cx(cx)
        if sp is None:
            continue
        rhs = [p.strip() for p in sp[2].split(".") if p.strip()]
        if len(rhs) != 1:            # 单产物，排除多组分/盐
            continue
        g = canon_key(rhs[0])
        if g is None:
            continue
        cs = g[0]
        if cs in seen:
            continue
        m = Chem.MolFromSmiles(cs)
        if m is None or Descriptors.MolWt(m) > 500 or m.GetNumHeavyAtoms() < 8:
            continue
        seen.add(cs)
        out.append(cs)
        if len(out) >= n:
            break
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 160
    t0 = time.time()
    print("=" * 92)
    print("受控评估：①可购砌块 对逆合成的净增益")
    print("=" * 92)

    tgt = sample_targets(n)
    print(f"目标分子 {len(tgt)} 个（ORD 真实产物，MW<=500，单组分）")

    tmpl = load_retro_templates()
    print(f"逆模板 {len(tmpl):,} 条（{time.time()-t0:.0f}s）")
    av = load_available()
    bf, bs = load_purchasable_blocks(with_reagents=False)
    print(f"终止集合 A(旧) {len(av):,}   B = A + 砌块 full {len(bf):,} / 骨架 {len(bs):,}")

    eng_a = RetroSearch(tmpl, av)
    eng_b = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs)
    # ★ ② 三档对照：
    #    B = 原始（无任何前体过滤，骨架匹配无重原子数护栏）
    #    C = 加"含试剂元素前体"过滤 + 骨架匹配重原子数护栏
    #    D = C + 再把带电小碎片前体也过滤掉
    eng_c = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                        filter_weird=True, skel_tol=1)
    eng_d = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                        filter_weird=True, weird_charged=True, skel_tol=1)
    # E = D + 惰性小分子前体过滤（S5，本轮新加）
    eng_e = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                        filter_weird=True, weird_charged=True, skel_tol=1,
                        filter_inert=True)
    eng_a.filter_weird = False                 # A 也不用前体过滤（保持与原口径一致）

    res = Counter()
    per_target = []
    t1 = time.time()
    for i, t in enumerate(tgt, 1):
        dis = eng_a.disconnections(t)           # 与终止集合无关，算一次
        if not dis:
            res["无切断方案"] += 1
            per_target.append({"target": t, "n_dis": 0})
            continue
        row = {"target": t, "n_dis": len(dis)}
        for name, eng in (("A", eng_a), ("B", eng_b), ("C", eng_c), ("D", eng_d),
                          ("E", eng_e)):
            full_hit = 0       # 至少有 1 个方案全部前体是终点
            best = 0
            for st in dis:
                avs = [eng.is_available(p) for p in st.precursors]
                k = sum(1 for a in avs if a)
                best = max(best, k)
                if k == len(st.precursors):
                    full_hit += 1
            row[f"{name}_full"] = full_hit
            row[f"{name}_best"] = best
            if full_hit:
                res[f"{name}_解决"] += 1
        per_target.append(row)
        if i % 20 == 0:
            el = time.time() - t1
            print(f"   {i}/{len(tgt)}  A {res['A_解决']} B {res['B_解决']} "
                  f"C {res['C_解决']} D {res['D_解决']} E {res['E_解决']}  ({el:.0f}s)",
                  flush=True)

    n_ok = len(tgt)
    print()
    print("=" * 92)
    print(f"结果（{n_ok} 个目标，{time.time()-t0:.0f}s）")
    print("=" * 92)
    def rate(k):
        return f"{res[k]:>4}/{n_ok}  ({res[k]/n_ok*100:5.1f}%)"
    print(f"  A 旧终止集合（无过滤）       一步到位 {rate('A_解决')}")
    print(f"  B 旧+①砌块（无过滤，原口径） 一步到位 {rate('B_解决')}")
    print(f"  C 旧+①砌块 +②护栏            一步到位 {rate('C_解决')}")
    print(f"  D C + 带电小碎片过滤          一步到位 {rate('D_解决')}")
    print(f"  E D + 惰性小分子前体过滤(②)   一步到位 {rate('E_解决')}")
    print()
    print(f"  ★ ①的净增益（B-A）        {res['B_解决']-res['A_解决']:+d}")
    print(f"  ★ ②护栏的代价（C-B）      {res['C_解决']-res['B_解决']:+d}   <- 应为 0 或很小")
    print(f"  ★ ②再过滤带电的代价（D-C）{res['D_解决']-res['C_解决']:+d}")
    print(f"  ★ ②过滤惰性小分子的代价（E-D）{res['E_解决']-res['D_解决']:+d}")
    print(f"  无切断方案 {res['无切断方案']} 个")
    loss = [r["target"] for r in per_target if r.get("B_full", 0) and not r.get("C_full", 0)]
    print(f"  ②护栏杀掉的目标（B有C无，前 8）: {loss[:8]}")

    OUT.write_text(json.dumps({
        "n_targets": n_ok,
        "solved_A": res["A_解决"], "solved_B": res["B_解决"],
        "solved_C": res["C_解决"], "solved_D": res["D_解决"],
        "solved_E": res["E_解决"], "rate_E": round(res["E_解决"] / n_ok, 4),
        "rate_A": round(res["A_解决"] / n_ok, 4),
        "rate_B": round(res["B_解决"] / n_ok, 4),
        "rate_C": round(res["C_解决"] / n_ok, 4),
        "rate_D": round(res["D_解决"] / n_ok, 4),
        "no_disconnection": res["无切断方案"],
        "targets": per_target,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
