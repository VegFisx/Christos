# -*- coding: utf-8 -*-
r"""决定性诊断：只把【模板库】换成新的 3,228 条，端到端一步到位率会变多少？

口径：
  目标   = 与 bench_blocks_value 完全相同的 160 个 ORD 产物（同随机种子、同筛选）
  模板A  = 现有 SmartReact 反转模板（9,770 条，"全跑一遍"）
  模板B  = 本轮新抽 + 聚类的 3,228 条（rdchiral 逆方向，无需反转）
  终止集合 = 旧(COCONUT+tcm.db) + ①砌块
  命中   = 有一个切断方案，其【全部前体】都在终止集合里
  两组都用同一套 is_available（含 S3/S5 护栏）

用法: python bench_new_templates.py [目标数]
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
from rdkit.Chem import Descriptors, rdChemReactions  # noqa: E402
from retro_search import (RetroSearch, load_available, load_retro_templates,  # noqa: E402
                          load_purchasable_blocks, canon)
from build_purchasable_blocks import BIG, split_cx, canon_key  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "bench_new_templates.json"
CLUSTERED = STAGE / "reports" / "retro_templates_clustered.jsonl"


def load_new_templates(path):
    """从聚类结果载入逆模板（已是 产物>>前体 方向，不需要反转）。"""
    out, bad, multi_prod = [], 0, 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            tpl = r["template"]
            try:
                rx = rdChemReactions.ReactionFromSmarts(tpl)
                if rx is None:
                    bad += 1
                    continue
                # 逆模板必须是"1 个目标 -> 前体"
                if rx.GetNumReactantTemplates() != 1:
                    multi_prod += 1
                    continue
                out.append(RetroTemplateNew(tpl, "rdchiral_retro", rx))
            except Exception:
                bad += 1
    return out, bad, multi_prod


class RetroTemplateNew:
    __slots__ = ("smarts", "name", "tid", "rxn")

    def __init__(self, smarts, name, rxn):
        self.smarts = smarts
        self.name = name
        self.tid = 0
        self.rxn = rxn


def sample_targets(n):
    """与 bench_blocks_value 相同的目标筛选（同种子）。"""
    import duckdb
    import random
    from ord_schema.proto import reaction_pb2
    con = duckdb.connect()
    con.execute("SET memory_limit='1500MB'")
    con.execute("SET threads=2")
    rows = con.execute(
        f"SELECT reaction FROM read_parquet('{BIG.as_posix()}') OFFSET 200000 LIMIT 40000"
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
        if len(rhs) != 1:
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


def eval_set(eng, targets, label):
    res = Counter()
    t0 = time.time()
    best_sum = 0
    for i, t in enumerate(targets, 1):
        dis = eng.disconnections(t)
        if not dis:
            res["无切断方案"] += 1
            continue
        full = 0
        best = 0
        for st in dis:
            avs = [eng.is_available(p) for p in st.precursors]
            k = sum(1 for a in avs if a)
            best = max(best, k)
            if k == len(st.precursors):
                full += 1
        best_sum += best
        if full:
            res["一步到位"] += 1
        elif best:
            res["部分前体可得"] += 1
        else:
            res["前体全都不可得"] += 1
        if i % 20 == 0:
            print(f"   [{label}] {i}/{len(targets)}  一步到位 {res['一步到位']}  "
                  f"({time.time()-t0:.0f}s)", flush=True)
    n = len(targets)
    print(f"\n   [{label}] 目标 {n}")
    print(f"      一步到位       {res['一步到位']:>4}/{n} ({res['一步到位']/n*100:5.1f}%)")
    print(f"      部分前体可得   {res['部分前体可得']:>4}/{n} ({res['部分前体可得']/n*100:5.1f}%)")
    print(f"      前体全都不可得 {res['前体全都不可得']:>4}/{n}")
    print(f"      无切断方案     {res['无切断方案']:>4}/{n}")
    print(f"      平均最佳可得前体数 {best_sum/max(n,1):.2f}")
    return res, n


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    t0 = time.time()
    print("=" * 92)
    print("决定性诊断：换模板库（不动搜索逻辑）能把端到端一步到位率拉多少？")
    print("=" * 92)

    tg = sample_targets(n)
    print(f"目标 {len(tg)} 个（与 bench_blocks_value 同口径）")

    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    print(f"终止集合：旧 {len(av):,} + 砌块 {len(bf):,}")

    old = load_retro_templates()
    print(f"模板A SmartReact反转：{len(old):,} 条")
    new, bad, multi = load_new_templates(CLUSTERED)
    print(f"模板B 新抽逆模板   ：{len(new):,} 条（编译失败 {bad}，多产物目标 {multi}）")

    eng_a = RetroSearch(old, av, blocks_full=bf, blocks_skel=bs,
                        filter_weird=True, weird_charged=True, skel_tol=1)
    eng_b = RetroSearch(new, av, blocks_full=bf, blocks_skel=bs,
                        filter_weird=True, weird_charged=True, skel_tol=1)

    print("\n" + "-" * 92)
    ra, na = eval_set(eng_a, tg, "模板A 旧")
    print("-" * 92)
    rb, nb = eval_set(eng_b, tg, "模板B 新")
    print("-" * 92)

    print()
    print("=" * 92)
    print(f"★ 一步到位率：旧模板 {ra['一步到位']/na*100:.1f}%  ->  新模板 {rb['一步到位']/nb*100:.1f}%")
    print(f"★ 砍掉模板数：{len(old):,} -> {len(new):,}（{len(new)/len(old)*100:.0f}%）")
    print("=" * 92)

    OUT.write_text(json.dumps({
        "n_targets": len(tg),
        "old_templates": len(old), "new_templates": len(new),
        "old": dict(ra), "new": dict(rb),
        "old_rate": round(ra["一步到位"] / na, 4),
        "new_rate": round(rb["一步到位"] / nb, 4),
        "elapsed_sec": round(time.time() - t0, 1),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {OUT.name}  {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
