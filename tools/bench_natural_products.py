# -*- coding: utf-8 -*-
r"""逆合成在【中药成分】上的可行性（决定能不能接进 TCMAI 的关键事实）。

口径：
  目标 = tcm.db compounds 里的分子（中药成分，天然产物尺度）
  测两件事：
   ① 能不能给出【可往下走的】切断方案（有前体、且至少 1 个前体是已知终端）
   ② 有多少目标能形成"全部前体都是终端"的一步路线
  对照组：上一轮 bench 的 160 个 ORD 药物化学产物（1.2% -> 5.0%）
用法: python bench_natural_products.py [目标数]
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
                          load_purchasable_blocks, ik)
from build_purchasable_blocks import inchi_keys_with_timeout  # noqa: E402

RDLogger.DisableLog("rdApp.*")
OUT = STAGE / "reports" / "bench_natural_products.json"


def load_np(n):
    from tcm_ro import use_readonly; use_readonly()
    from db_utils import open_db
    rows = []
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name_en, smiles, mol_weight FROM compounds "
                    "WHERE smiles IS NOT NULL AND smiles != ''")
        allr = cur.fetchall()
    random.seed(20261011)
    random.shuffle(allr)
    out, seen = [], set()
    for en, smi, mw in allr:
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        w = Descriptors.MolWt(m)
        if w < 200 or w > 600:          # 天然产物主区间
            continue
        cs = Chem.MolToSmiles(m)
        if cs in seen:
            continue
        seen.add(cs)
        out.append((en or "?", cs, round(w, 1)))
        if len(out) >= n:
            break
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    t0 = time.time()
    print("=" * 90)
    print("逆合成在【中药成分】上的可行性")
    print("=" * 90)
    tg = load_np(n)
    print(f"目标 {len(tg)} 个（tcm.db 成分，MW 200~600）")
    for nm, cs, w in tg[:5]:
        print(f"   例: {nm[:20]:<20} MW{w:6.1f}  {cs[:60]}")

    tmpl = load_retro_templates()
    av = load_available()
    bf, bs = load_purchasable_blocks(with_reagents=False)
    eng = RetroSearch(tmpl, av, blocks_full=bf, blocks_skel=bs)
    print(f"逆模板 {len(tmpl):,}；终端集合 旧{len(av):,} + 砌块{len(bf):,}")

    res = Counter()
    per = []
    t1 = time.time()
    for i, (nm, cs, w) in enumerate(tg, 1):
        dis = eng.disconnections(cs)
        row = {"name": nm, "smiles": cs, "MW": w, "n_dis": len(dis),
               "n_all_terminal": 0, "n_some_terminal": 0,
               "n_forward_ok": 0, "example": None}
        if dis:
            for st in dis:
                avs = [eng.is_available(p) for p in st.precursors]
                k = sum(1 for a in avs if a)
                if k == len(st.precursors):
                    row["n_all_terminal"] += 1
                if k:
                    row["n_some_terminal"] += 1
            if row["n_some_terminal"] and row["example"] is None:
                best = max(dis, key=lambda st: sum(1 for p in st.precursors
                                                   if eng.is_available(p)))
                row["example"] = {"reaction": best.reaction_name,
                                  "precursors": list(best.precursors)}
        if row["n_all_terminal"]:
            res["一步到位"] += 1
        elif row["n_some_terminal"]:
            res["部分前体可得"] += 1
        elif dis:
            res["有切断但前体都不可得"] += 1
        else:
            res["无切断方案"] += 1
        per.append(row)
        if i % 20 == 0:
            el = time.time() - t1
            print(f"   {i}/{len(tg)}  一步到位 {res['一步到位']}  "
                  f"部分可得 {res['部分前体可得']}  ({el:.0f}s)", flush=True)

    print()
    print("=" * 90)
    print(f"结果（{len(tg)} 个中药成分，{time.time()-t0:.0f}s）")
    print("=" * 90)
    for k in ("一步到位", "部分前体可得", "有切断但前体都不可得", "无切断方案"):
        v = res[k]
        print(f"   {k:<20} {v:>4}/{len(tg)}  ({v/len(tg)*100:5.1f}%)")
    print()
    print("   有切断方案但【没一个前体是已知终端】的比例很高的话，")
    print("   说明瓶颈在终端集合(可买性)而不是模板；反之则是模板问题。")
    print()
    print("   部分前体可得的例子（前 6 个）:")
    shown = 0
    for r in per:
        if r["example"] and shown < 6:
            print(f"     {r['name'][:18]:<18} MW{r['MW']:6.1f} 切断{r['n_dis']:>5}个  "
                  f"[{r['example']['reaction']}]")
            print(f"        前体 {str(r['example']['precursors'])[:100]}")
            shown += 1
    OUT.write_text(json.dumps({"n": len(tg), "summary": dict(res), "targets": per},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n-> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
