# -*- coding: utf-8 -*-
r"""C 试点：给 top mined 模板直接从 ORD 记录建条件窗口（不依赖 37 类）。

做法：
  1. 按 support 取 top N mined 模板；
  2. 对 ORD 索引等距抽样，逐条把模板套到反应物上；
  3. 只有生成片段与记录真实产物相同才收集该记录条件（temp/catalyst/solvent）。

输出：
  data\mined_top_template_conditions.json
  reports\第七十五轮-mined模板条件窗口（TopN）.md

不打分、不排序；top N 只是按 support 取候选，报告内按输入顺序列示。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from itertools import permutations
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

STAGE = Path(__file__).resolve().parent.parent
FULL = STAGE / "reports" / "mined_forward_templates_full_lf.jsonl"
INDEX = STAGE / "data" / "ord_reaction_index.jsonl"
OUTJ = STAGE / "data" / "mined_top_template_conditions.json"
OUTM = STAGE / "reports" / "第七十五轮-mined模板条件窗口（TopN）.md"


def canon_plain(mol) -> str:
    if mol is None:
        return ""
    try:
        m = Chem.Mol(mol)
        m = Chem.RemoveHs(m, sanitize=False)
    except Exception:
        return ""
    for a in m.GetAtoms():
        a.SetAtomMapNum(0)
    try:
        Chem.SanitizeMol(m)
    except Exception:
        pass
    try:
        return Chem.MolToSmiles(m, isomericSmiles=False)
    except Exception:
        return ""


def canons_of(mol) -> set:
    out = set()
    s = canon_plain(mol)
    if s:
        out.add(s)
    try:
        frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=False)
    except Exception:
        frags = []
    for f in frags:
        s = canon_plain(f)
        if s:
            out.add(s)
    return out


def temp_num(s: str):
    p = str(s or "").split()
    if not p:
        return None
    try:
        return float(p[0])
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--out-json", default=str(OUTJ))
    ap.add_argument("--out-md", default=str(OUTM))
    args = ap.parse_args()

    cand = []
    with FULL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            cand.append((int(d.get("support") or 0), str(d.get("template") or "")))
    cand.sort(key=lambda x: -x[0])
    cand = cand[:max(1, args.top)]
    objs = []
    for sup, sm in cand:
        try:
            rxn = AllChem.ReactionFromSmarts(sm)
        except Exception:
            rxn = None
        if rxn is None:
            continue
        objs.append({
            "support": sup, "template": sm, "rxn": rxn,
            "n": rxn.GetNumReactantTemplates(),
            "tpls": [rxn.GetReactantTemplate(i)
                     for i in range(rxn.GetNumReactantTemplates())],
            "fired": 0, "match": 0,
            "n_temp": 0, "n_cat": 0, "n_sol": 0, "n_reag": 0, "n_any": 0,
            "temps": Counter(), "cats": Counter(), "sols": Counter(),
            "reags": Counter(), "examples": [],
        })
    print("top 模板 %d 条（解析成功 %d）" % (len(cand), len(objs)))

    total = 0
    with INDEX.open(encoding="utf-8") as fh:
        idx = -1
        for line in fh:
            idx += 1
            if idx % 29:
                continue
            if total >= args.limit:
                break
            total += 1
            try:
                rec = json.loads(line)
            except Exception:
                continue
            mols = []
            for smi in rec.get("reactants") or []:
                m = Chem.MolFromSmiles(smi)
                if m is not None:
                    mols.append(m)
            if not mols:
                continue
            actual = set()
            for smi in rec.get("products") or []:
                m = Chem.MolFromSmiles(smi)
                if m is not None:
                    actual |= canons_of(m)
            if not actual:
                continue
            for o in objs:
                rxn = o["rxn"]
                tpls = o["tpls"]
                hits = []
                for tpl in tpls:
                    hits.append([i for i, m in enumerate(mols)
                                 if m.HasSubstructMatch(tpl)])
                if any(not h for h in hits):
                    continue
                matched = fired = False
                if o["n"] == 1:
                    pairs = [(i,) for i in hits[0]]
                elif o["n"] == 2:
                    pairs = [(i, j) for i in hits[0] for j in hits[1]
                             if i != j]
                else:
                    pairs = []
                for idxs in pairs:
                    try:
                        prods = rxn.RunReactants(tuple(mols[i] for i in idxs))
                    except Exception:
                        continue
                    for pt in prods:
                        for pm in pt:
                            cs = canons_of(pm)
                            if not cs:
                                continue
                            fired = True
                            if cs & actual:
                                matched = True
                                break
                        if matched:
                            break
                    if matched:
                        break
                if fired:
                    o["fired"] += 1
                if matched:
                    o["match"] += 1
                    temp = str(rec.get("temp") or "")
                    cats = rec.get("catalysts") or []
                    sols = rec.get("solvents") or []
                    reags = rec.get("reagents") or []
                    if temp:
                        o["n_temp"] += 1; o["temps"][temp] += 1
                    if cats:
                        o["n_cat"] += 1
                        for x in cats:
                            o["cats"][x] += 1
                    if sols:
                        o["n_sol"] += 1
                        for x in sols:
                            o["sols"][x] += 1
                    if reags:
                        o["n_reag"] += 1
                        for x in reags:
                            o["reags"][x] += 1
                    if temp or cats or sols or reags:
                        o["n_any"] += 1
                    if len(o["examples"]) < 3:
                        o["examples"].append({
                            "rid": rec.get("rid"), "temp": temp,
                            "catalysts": cats, "solvents": sols,
                            "reagents": reags,
                        })
            if total % 5000 == 0:
                print("  ... %d/%d" % (total, args.limit), flush=True)

    rows = []
    for o in objs:
        temps = [temp_num(x) for x in o["temps"]]
        temps = [x for x in temps if x is not None]
        rows.append({
            "template": o["template"], "support": o["support"],
            "n_templates": o["n"], "fired": o["fired"], "match": o["match"],
            "n_temp": o["n_temp"], "n_catalyst": o["n_cat"],
            "n_solvent": o["n_sol"], "n_reagent": o["n_reag"],
            "n_any": o["n_any"],
            "temps": dict(o["temps"].most_common(20)),
            "temps_min": min(temps) if temps else None,
            "temps_max": max(temps) if temps else None,
            "catalysts": dict(o["cats"].most_common(20)),
            "solvents": dict(o["sols"].most_common(20)),
            "reagents": dict(o["reags"].most_common(20)),
            "examples": o["examples"],
        })
    Path(args.out_json).write_text(json.dumps({
        "top": args.top, "scanned": total, "rows": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    with Path(args.out_md).open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · mined 模板条件窗口（Top%d）\n\n" % args.top)
        f.write("> 按 support 取 top 模板；对 ORD 索引前 %d 条等距样本试跑；"
                "只有产物与记录一致才收集条件。\n" % total)
        f.write("> 这是 per-template 条件窗口，不依赖 37 类反应表。\n\n")
        f.write("| # | support | 模板 | fired | match | 温度 | 催化剂 | 溶剂 | 试剂 |\n")
        f.write("|---|---:|---|---:|---:|---|---|---|---|\n")
        for i, r in enumerate(rows, 1):
            f.write("| %d | %d | `%s` | %d | %d | %d | %d | %d | %d |\n"
                    % (i, r["support"], r["template"][:80], r["fired"],
                       r["match"], r["n_temp"], r["n_catalyst"],
                       r["n_solvent"], r["n_reagent"]))
        f.write("\n## 有条件的模板（前 30）\n\n")
        for r in [x for x in rows if x["n_any"]][:30]:
            f.write("### support %d · `%s`\n\n"
                    % (r["support"], r["template"]))
            f.write("* fired %d / match %d；温度 %d / 催化剂 %d / 溶剂 %d / 试剂 %d\n"
                    % (r["fired"], r["match"], r["n_temp"],
                       r["n_catalyst"], r["n_solvent"], r["n_reagent"]))
            f.write("* 温度：%s\n" % (r["temps"] or "—"))
            f.write("* 催化剂：%s\n" % (r["catalysts"] or "—"))
            f.write("* 溶剂：%s\n" % (r["solvents"] or "—"))
            f.write("* 示例：%s\n\n" % (r["examples"][:1] or "—"))

    print("-> %s" % args.out_json)
    print("-> %s" % args.out_md)
    print("  top %d ｜ scanned %d ｜ 有 match 模板 %d"
          % (len(rows), total, sum(1 for r in rows if r["match"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
