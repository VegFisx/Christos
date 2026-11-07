# -*- coding: utf-8 -*-
r"""假阳性核查：逆合成给出的"可得前体"到底有几个是真的？

动机：中药成分那轮里出现
    'CC'（乙烷）、'CO'（甲醇）、'CCl'（氯甲烷）被当成终端，
    还有一个带 Br 的陌生骨架被当成"可得"。
    这些在化学上是假的 —— 必须量化有多少。

口径（三档，严格递进）
  A 真·同一分子 : full InChIKey 命中 COCONUT/tcm.db/砌块
  B 骨架命中     : 只有 InChIKey 前 14 位命中（构型或取代可能不同）-> 可疑
  C 假阳性       : 命中了，但【该分子本身作为产物在 ORD 出现过】
                   = 化学家其实要合成它 -> 把它当终点是错的
另计：前体太小（重原子<=2，如甲醇/乙烷/氯甲烷）单独列，这是"无合成意义"

用法: python verify_retro_false_positive.py [目标数]
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

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors  # noqa: E402
from retro_search import (RetroSearch, load_available, load_retro_templates,  # noqa: E402
                          load_purchasable_blocks, ik, canon)
from build_purchasable_blocks import inchi_keys_with_timeout  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "retro_false_positive.json"
CACHE_P = STAGE / "reports" / "_prod_smiles_cache.txt"      # 全部产物分子（上一轮已建）


def load_np(n):
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import open_db
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name_en, smiles FROM compounds "
                    "WHERE smiles IS NOT NULL AND smiles != ''")
        allr = cur.fetchall()
    random.seed(20261011)
    random.shuffle(allr)
    out, seen = [], set()
    for en, smi in allr:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        w = Descriptors.MolWt(m)
        if w < 200 or w > 600:
            continue
        cs = Chem.MolToSmiles(m)
        if cs in seen:
            continue
        seen.add(cs)
        out.append((en or "?", cs))
        if len(out) >= n:
            break
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    t0 = time.time()
    print("=" * 92)
    print("假阳性核查：逆合成说'可得'的前体，有多少是真的")
    print("=" * 92)

    tg = load_np(n)
    tmpl = load_retro_templates()
    av = load_available()
    bf, bs = load_purchasable_blocks(False)
    # ★ ② 三档对照：C0 = 无护栏（原状）；C1 = 加骨架重原子数护栏；C2 = 再加带电小碎片过滤
    engs = {
        "C0_无护栏": RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                                filter_weird=False, skel_tol=99, weird_charged=False),
        "C1_骨架护栏": RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                                  filter_weird=False, skel_tol=1, weird_charged=False),
        "C2_骨架+带电": RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                                   filter_weird=True, skel_tol=1, weird_charged=True),
    }
    eng = engs["C0_无护栏"]

    # 产物分子全集（用于判 C：该分子在 ORD 里作为产物出现过 = 其实要合成）
    prod_keys = set()
    if CACHE_P.exists():
        prod_keys = set(CACHE_P.read_text(encoding="utf-8").splitlines())
        print(f"读产物分子缓存 {len(prod_keys):,}")
    else:
        print("   [warn] 没有产物缓存，C 档无法判")

    res = Counter()
    rows = []
    per_eng = {}
    for label, e in engs.items():
        per_eng[label] = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs,
                                     filter_weird=e.filter_weird,
                                     weird_charged=e.weird_charged,
                                     skel_tol=e.skel_tol)
    for i, (nm, cs) in enumerate(tg, 1):
        dis_base = eng.disconnections(cs)
        dis_by = {"C0_无护栏": dis_base}
        for label in ("C1_骨架护栏", "C2_骨架+带电"):
            dis_by[label] = per_eng[label].disconnections(cs)
        for label, dl in dis_by.items():
            e = per_eng[label]
            routes = []
            for st in dl:
                hits = [(p, e.is_available(p), e._match_level.get(p, ""))
                        for p in st.precursors]
                if all(h[1] for h in hits):
                    routes.append((st, hits))
            res[f"{label}_目标数"] += 1
            if not routes:
                continue
            res[f"{label}_有一步路线"] += 1
            if label != "C0_无护栏":
                continue                       # 可疑前体只统计 C0，避免重复
            res["有一步路线目标"] += 1
            for st, hits in routes[:3]:        # 每个目标最多查 3 条
                for p, tag, level in hits:
                    res["前体总检查数"] += 1
                    res[f"档:{level or '未知'}"] += 1
                    m = Chem.MolFromSmiles(p)
                    hac = m.GetNumHeavyAtoms() if m else -1
                    if hac <= 2:
                        res["太小(<=2重原子)"] += 1
                    k = ik(p)
                    if k and k in prod_keys:
                        res["★假阳性(该分子在ORD作产物出现过)"] += 1
                    if level == "block_skel":
                        res["骨架命中(可疑)"] += 1
                    rows.append({"target": nm, "target_smiles": cs,
                                 "reaction": st.reaction_name,
                                 "precursor": p, "tag": tag, "level": level,
                                 "heavy_atoms": hac,
                                 "in_ord_products": bool(k and k in prod_keys)})
        if i % 20 == 0:
            line = "  ".join(f"{l.split('_')[0]}:{res[l+'_有一步路线']}" for l in engs)
            print(f"   {i}/{len(tg)}  有一步路线 {line}  ({time.time()-t0:.0f}s)", flush=True)

    print()
    print("=" * 92)
    print(f"结果（{len(tg)} 个中药成分）")
    print("=" * 92)
    print("  各档'有一步路线'的中药成分数：")
    for label in engs:
        v = res[f"{label}_有一步路线"]
        print(f"     {label:<12} {v:>3}/{len(tg)}  ({v/len(tg)*100:5.1f}%)")
    print("\n  以下可疑前体统计基于 C0（无护栏）口径，共 "
          f"{res['有一步路线目标']} 个目标有路线")
    tot = res["前体总检查数"]
    for k in ("前体总检查数", "档:old_terminal", "档:block_full", "档:block_skel",
              "太小(<=2重原子)", "骨架命中(可疑)",
              "★假阳性(该分子在ORD作产物出现过)"):
        v = res[k]
        pct = f"  ({v/tot*100:5.1f}%)" if tot and k != "前体总检查数" else ""
        print(f"   {k:<34} {v:>5}{pct}")
    print()
    bad = res["太小(<=2重原子)"] + res["★假阳性(该分子在ORD作产物出现过)"] + res["骨架命中(可疑)"]
    print(f"   ★ 三者取并集的上界 {bad}/{tot} = {bad/max(tot,1)*100:.1f}% —— "
          f"这些'可得'需要打折看")
    print()
    print("   可疑例子:")
    shown = 0
    for r in rows:
        if (r["heavy_atoms"] <= 2 or r["in_ord_products"] or r["level"] == "block_skel") and shown < 10:
            why = []
            if r["heavy_atoms"] <= 2:
                why.append("太小")
            if r["in_ord_products"]:
                why.append("ORD里作过产物")
            if r["level"] == "block_skel":
                why.append("骨架命中")
            print(f"     [{','.join(why)}] {r['target'][:16]:<16} <- {r['precursor'][:52]}")
            shown += 1
    OUT.write_text(json.dumps({"n_targets": len(tg), "summary": dict(res),
                               "pairs": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
