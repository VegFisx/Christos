# -*- coding: utf-8 -*-
r"""★ 端到端：药材成分 → 预测反应与产物（双源版：tcm.db + COCONUT）★

改动要点（修 2026-10-11 用户指出的疏漏）：
  1. 改走 `collect_compounds()`【双源统一入口】，不再只用 HERB 一半
  2. ★ 透明报告「可用 vs 实际取用」★，不再静默只用少数成分
  3. 用 np_likeness / chemical_class 排序与标注
  4. "命中已知成分"改用 COCONUT（272,992 个）为参照库，tcm.db 作补充

用法:
  python predict_herb_reactions.py 甘草
  python predict_herb_reactions.py 甘草 --limit 150 --out reports/gancao
"""
import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, r"D:\TCMAI\src")

import sqlite3  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import Descriptors, rdMolDescriptors  # noqa: E402
from smartreact import ReactionEnumerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

from tcm_ro import use_readonly; use_readonly()
from db_utils import open_db, collect_compounds  # noqa: E402

COCONUT_DB = Path(r"D:\TCMAI\coconut.db")
COCO_INDEX = STAGE / "reports" / "coconut_inchikey_index.jsonl"


def canon(smi):
    try:
        m = Chem.MolFromSmiles(smi)
        return Chem.MolToSmiles(m) if m is not None else None
    except Exception:
        return None


def load_tcm_known():
    """tcm.db 已知成分：inchi_key -> name"""
    known = {}
    with open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT inchi_key, name_en FROM compounds "
                    "WHERE inchi_key IS NOT NULL AND inchi_key != ''")
        for ik, nm in cur.fetchall():
            if ik and ik not in known:
                known[ik] = nm or "(未命名)"
    return known


def load_coconut_index():
    """COCONUT 参照库：inchi_key -> (name, np_likeness, chemical_class)"""
    if not COCO_INDEX.exists():
        print(f"[warn] COCONUT 索引不存在: {COCO_INDEX}")
        print("       先跑 tools\\build_coconut_index.py；本次只用 tcm.db 作参照")
        return {}
    idx = {}
    with open(COCO_INDEX, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 4 and p[0] not in idx:
                try:
                    npl = float(p[2]) if p[2] else None
                except ValueError:
                    npl = None
                idx[p[0]] = (p[1] or "(未命名)", npl, p[3])
    return idx


def enrich_np_likeness(comps):
    """给 COCONUT 来源的成分补上 np_likeness / chemical_class。

    注意：db_utils.find_compounds_coconut 把 np_likeness SELECT 出来又丢掉了，
    所以这里自己按 cnp_id 补查。
    """
    cnp_ids = [c["ingredient_id"] for c in comps if c.get("match_level") == "coconut"]
    if not cnp_ids:
        return
    info = {}
    con = sqlite3.connect(f"file:{COCONUT_DB}?mode=ro", uri=True)
    cur = con.cursor()
    CH = 900
    for i in range(0, len(cnp_ids), CH):
        chunk = cnp_ids[i:i + CH]
        ph = ",".join("?" * len(chunk))
        cur.execute(f"SELECT cnp_id, np_likeness, chemical_class, chemical_super_class "
                    f"FROM compounds WHERE cnp_id IN ({ph})", chunk)
        for cnp, npl, cls, sup in cur.fetchall():
            info[cnp] = (npl, cls, sup)
    con.close()
    for c in comps:
        if c.get("match_level") == "coconut":
            npl, cls, sup = info.get(c["ingredient_id"], (None, None, None))
            c["np_likeness"] = npl
            c["chemical_class"] = cls
            c["chemical_super_class"] = sup


def pick_inputs(comps, n):
    """透明地从双源候选里挑 n 个：两源各取一半，避免某源被整体丢掉。"""
    herb = [c for c in comps if c.get("match_level") != "coconut"]
    coco = [c for c in comps if c.get("match_level") == "coconut"]
    herb.sort(key=lambda c: -(c.get("mol_weight") or 0))
    coco.sort(key=lambda c: -(c.get("np_likeness") or -99))
    half = max(1, n // 2)
    sel = herb[:half] + coco[:n - len(herb[:half])]
    if len(sel) < n:
        rest = [c for c in (herb[half:] + coco[n - len(herb[:half]):])]
        sel += rest[:n - len(sel)]
    return sel, len(herb), len(coco)


def cond_cell(entry):
    if not entry:
        return "无条件数据"
    parts = []
    t = entry.get("temp_C")
    if t:
        unit = (t.get("units") or ["CELSIUS"])[0]
        sym = "°C" if "CELSIUS" in unit else unit
        parts.append(f"温度 {t['median']}{sym}（{t['min']}~{t['max']}，n={t['n']}）"
                     if t["min"] != t["max"] else f"温度 {t['median']}{sym}")
    if entry.get("controls"):
        parts.append("控温 " + " / ".join(entry["controls"][:2]))
    tm = entry.get("time_min")
    if tm:
        if tm["median"] >= 60:
            parts.append(f"时间 {tm['median']/60:.1f} 小时（n={tm['n']}）")
        else:
            parts.append(f"时间 {tm['median']} 分钟（n={tm['n']}）")
    if entry.get("solvents"):
        parts.append("溶剂 " + " / ".join(entry["solvents"][:3]))
    if entry.get("catalysts"):
        parts.append("催化剂 " + " / ".join(entry["catalysts"][:3]))
    if entry.get("bases"):
        parts.append("碱 " + " / ".join(entry["bases"][:2]))
    if entry.get("reagents"):
        parts.append("试剂 " + " / ".join(entry["reagents"][:3]))
    if entry.get("auxiliary_reagents"):
        parts.append("**辅助试剂** " + " / ".join(entry["auxiliary_reagents"][:3]))
    p = entry.get("ph")
    if p:
        parts.append(f"pH {p['median']}（{p['min']}~{p['max']}）")
    return "；".join(parts) if parts else "**无 ORD 条件数据**"


def load_conditions():
    p = STAGE / "reports" / "conditions_by_reaction_type.json"
    if not p.exists():
        print(f"[warn] 条件表不存在: {p}")
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("herb", nargs="?", default="甘草")
    ap.add_argument("--limit", type=int, default=120, help="实际取用多少个成分")
    ap.add_argument("--herb-limit", type=int, default=600, help="HERB 源候选上限")
    ap.add_argument("--coconut-limit", type=int, default=3000, help="COCONUT 源候选上限")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print("=" * 92)
    print(f"药材成分 → 反应预测（双源）：{args.herb}")
    print("=" * 92)

    # ---------- 1. 双源取成分 ----------
    t0 = time.time()
    comps, missed = collect_compounds([args.herb], herb_limit=args.herb_limit,
                                      coconut_limit=args.coconut_limit,
                                      return_missed=True)
    print(f"collect_compounds 双源取数耗时 {time.time()-t0:.1f}s   未命中={missed}")
    if not comps:
        print(f"✗ 查不到「{args.herb}」的成分")
        return 1
    print("回查 np_likeness …")
    enrich_np_likeness(comps)

    n_all = len(comps)
    n_herb_raw = sum(1 for c in comps if c.get("match_level") != "coconut")
    n_coco_raw = sum(1 for c in comps if c.get("match_level") == "coconut")
    print(f"★ 双源去重后可用成分 {n_all} 个（HERB {n_herb_raw} + COCONUT {n_coco_raw}）")

    sel, _, _ = pick_inputs(comps, args.limit)
    n_sel = len(sel)
    print(f"★ 本次实际取用 {n_sel} 个  = 可用量的 {n_sel/n_all*100:.1f}%"
          f"   ← 这个比例必须透明（之前静默用了 1.2%）")
    print(f"   选取规则：HERB 按分子量降序、COCONUT 按 np_likeness 降序，两源各半\n")

    mols = []
    for c in sel:
        cs = canon(c.get("smiles"))
        if cs:
            mols.append({"smiles": cs, "name": c.get("name") or "(未命名)",
                         "mw": c.get("mol_weight"),
                         "src": "COCONUT" if c.get("match_level") == "coconut" else "HERB",
                         "npl": c.get("np_likeness"),
                         "cls": c.get("chemical_class")})
    mols = list({m["smiles"]: m for m in mols}.values())
    print(f"可枚举成分 {len(mols)} 个（去重后）")

    # ---------- 2. 枚举 ----------
    enum = ReactionEnumerator()
    pairs = [(i, j) for i in range(len(mols)) for j in range(i + 1, len(mols))]
    print(f"两两配对 {len(pairs)} 对，开始枚举…")

    prods = defaultdict(lambda: {"tmpl": set(), "pairs": set()})
    type_pairs = Counter()
    type_prod_seen = set()
    t0 = time.time()
    BATCH = 500
    for b in range(0, len(pairs), BATCH):
        chunk = pairs[b:b + BATCH]
        pay = [(mols[i]["smiles"], mols[j]["smiles"]) for i, j in chunk]
        try:
            results = enum.enumerate_pairs(pay)
        except Exception:
            continue
        seen_types = set()
        for r in results:
            for p in r.products:
                cp = canon(p)
                if not cp or cp in (r.reactant_a, r.reactant_b):
                    continue
                e = prods[cp]
                e["tmpl"].add(r.reaction_name)
                type_prod_seen.add((r.reaction_name, cp))
            seen_types.add(r.reaction_name)
        for t in seen_types:
            type_pairs[t] += 1
        if (b // BATCH) % 10 == 0:
            el = time.time() - t0
            print(f"   {b+len(chunk)}/{len(pairs)}  已用 {el:.0f}s  产物 {len(prods)}",
                  flush=True)
    for t, _cp in type_prod_seen:
        pass
    type_prods = Counter(t for t, _ in type_prod_seen)
    print(f"枚举完成，耗时 {time.time()-t0:.1f}s")
    print(f"★ 去重后预测产物 {len(prods)} 个\n")

    # ---------- 3. 回查已知成分（COCONUT 为主，tcm.db 补充）----------
    print("回查已知天然产物…")
    tcm_known = load_tcm_known()
    coco_idx = load_coconut_index()
    print(f"   tcm.db  {len(tcm_known):,} 个 inchi_key")
    print(f"   COCONUT {len(coco_idx):,} 个 inchi_key")

    hits = {}
    for cp in prods:
        m = Chem.MolFromSmiles(cp)
        if m is None:
            continue
        try:
            ik = Chem.MolToInchiKey(m)
        except Exception:
            continue
        if not ik:
            continue
        if ik in coco_idx:
            nm, npl, cls = coco_idx[ik]
            hits[cp] = ("COCONUT", nm, npl, cls)
        elif ik in tcm_known:
            hits[cp] = ("tcm.db", tcm_known[ik], None, None)
    n_coco_hit = sum(1 for v in hits.values() if v[0] == "COCONUT")
    n_tcm_hit = len(hits) - n_coco_hit
    print(f"★ 命中【已知天然产物】：{len(hits)} 个"
          f"（COCONUT {n_coco_hit} + tcm.db {n_tcm_hit}）\n")

    # ---------- 4. 排序 ----------
    def key(kv):
        cp, e = kv
        h = hits.get(cp)
        return (0 if h and h[0] == "COCONUT" else 1 if h else 2,
                -len(e["tmpl"]), -len(e["pairs"]))
    ranked = sorted(prods.items(), key=key)

    # ---------- 5. 输出 ----------
    conds = load_conditions()
    outpre = Path(args.out) if args.out else STAGE / "reports" / f"predict_{args.herb}"
    outpre.parent.mkdir(parents=True, exist_ok=True)
    csv_p, md_p = outpre.with_suffix(".csv"), outpre.with_suffix(".md")

    with open(csv_p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["产物SMILES", "分子式", "分子量", "模板数", "涉及反应类型",
                    "反应条件(来自ORD)", "命中类别", "已知名称", "np_likeness",
                    "chemical_class"])
        for cp, e in ranked:
            m = Chem.MolFromSmiles(cp)
            if m is None:
                continue
            types = sorted(e["tmpl"])
            ctext = " | ".join(f"{t}: {cond_cell(conds.get(t, {}))}" for t in types)
            h = hits.get(cp)
            w.writerow([cp, rdMolDescriptors.CalcMolFormula(m),
                        round(Descriptors.MolWt(m), 2), len(e["tmpl"]),
                        ";".join(types), ctext,
                        h[0] if h else "", h[1] if h else "",
                        ("" if not h or h[2] is None else h[2]),
                        (h[3] or "") if h else ""])

    L = []
    L.append(f"# {args.herb} —— 成分间反应预测（双源）\n")
    L.append(f"- 数据源：`tcm.db` + `coconut.db` **双源**（`collect_compounds`），真实数据非手写")
    L.append(f"- 双源去重后**可用成分 {n_all} 个**（HERB {n_herb_raw} + COCONUT {n_coco_raw}）")
    L.append(f"- **本次实际取用 {n_sel} 个 = 可用量的 {n_sel/n_all*100:.1f}%**"
             f"（HERB 按分子量降序、COCONUT 按 np_likeness 降序，两源各半）")
    L.append(f"- 两两配对 **{len(pairs)}** 对；规则库 SmartReact **9770** 条模板")
    L.append(f"- 去重后预测产物 **{len(prods)}** 个")
    L.append(f"- **命中已知天然产物 {len(hits)} 个**（COCONUT 参照库 {len(coco_idx):,} 个"
             f" + tcm.db {len(tcm_known):,} 个）\n")

    L.append("## 一、本次触发的反应类型及其反应条件\n")
    L.append("条件来自 **ORD 真实实验数据**（统计被该类型复现的反应实际用了什么），非手写；"
             "无数据会明确标注。**条件只作标注，不筛除任何反应。**\n")
    L.append("| 反应类型 | 参与的配对数 | 该类型产物数 | 反应条件（来自 ORD） | ORD证据数 |")
    L.append("|---|---|---|---|---|")
    for t, c in type_pairs.most_common():
        e = conds.get(t, {})
        L.append(f"| `{t}` | {c} | {type_prods.get(t, 0)} | {cond_cell(e)} | "
                 f"{e.get('n_ord_matched', 0)} |")

    L.append(f"\n## 二、命中【已知天然产物】的预测产物（最强证据）\n")
    if hits:
        L.append("| 预测产物 | 分子式 | 来源 | 已知名称 | np_likeness | chemical_class | 反应类型 |")
        L.append("|---|---|---|---|---|---|---|")
        for cp, e in ranked:
            h = hits.get(cp)
            if not h:
                continue
            m = Chem.MolFromSmiles(cp)
            L.append(f"| `{cp[:52]}` | {rdMolDescriptors.CalcMolFormula(m)} | {h[0]} | "
                     f"**{h[1]}** | {'' if h[2] is None else h[2]} | {h[3] or ''} | "
                     f"{';'.join(sorted(e['tmpl']))[:40]} |")
    else:
        L.append("（本次无命中）")

    L.append(f"\n## 三、置信度最高的预测产物（多模板共识，前 40）\n")
    L.append("| 产物 | 分子式 | 分子量 | 模板数 | 命中 | 反应类型 |")
    L.append("|---|---|---|---|---|---|")
    for cp, e in ranked[:40]:
        m = Chem.MolFromSmiles(cp)
        if m is None:
            continue
        h = hits.get(cp)
        L.append(f"| `{cp[:50]}` | {rdMolDescriptors.CalcMolFormula(m)} | "
                 f"{Descriptors.MolWt(m):.1f} | {len(e['tmpl'])} | "
                 f"{h[1][:22] if h else ''} | {';'.join(sorted(e['tmpl']))[:44]} |")

    L.append("\n---\n\n## 这个工具能做什么、不能做什么\n")
    L.append("**能**：对给定药材，从 **tcm.db + COCONUT 双源**取真实成分，"
             "穷举两两之间的单步反应，给出产物、反应类型、**ORD 实测条件**，"
             "并把产物回查 **27 万个已知天然产物**作佐证。\n")
    L.append("**不能**（重要）：\n")
    L.append("1. **只覆盖单步、双组分**反应。多步级联、三组分以上、分子内环化做不到。")
    L.append("2. **对真实文献反应覆盖率约 30%**（ORD 177 万条实测）→ 没预测出来 ≠ 不会发生。")
    L.append("3. **条件只标注、不做筛选**（按用户 2026-10-11 要求）→ "
             "产物里会有**化学上不可能**的（如无 PPh₃ 的 Mitsunobu）。这是已知缺陷。")
    L.append("4. **不判断热力学/动力学可行性**。能枚举 ≠ 真会发生。")
    L.append("5. **无假阳性率数据**（缺负样本），无法给精确率。\n")
    L.append(f"明细：`{csv_p.name}`\n")

    md_p.write_text("\n".join(L), encoding="utf-8")
    print("=" * 92)
    print(f"报告: {md_p}")
    print(f"明细: {csv_p}")
    print("=" * 92)
    print(f"产物 {len(prods)} 个，命中已知天然产物 {len(hits)} 个 "
          f"(COCONUT {n_coco_hit} / tcm.db {n_tcm_hit})")
    for cp, h in list(hits.items())[:10]:
        print(f"   [{h[0]}] {h[1][:34]:<34} npl={h[2]}  {cp[:52]}")
    enum.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
