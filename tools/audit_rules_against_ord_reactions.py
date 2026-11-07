# -*- coding: utf-8 -*-
r"""规则来源体检（待办 2 · 方案 b）：把规则套到 ORD 真实反应上。

与方案 a（模板签名比对）不同，这里直接做**前向试跑**：

  * 对 `data\ord_reaction_index.jsonl` 做**等距抽样**（默认 6 万条）；
  * 64 条规则逐条套到该记录的反应物上；
  * 生成产物按「去映射号、去显式 H、去立体、拆片段」规范化；
  * 若生成片段与记录里的真实产物相同，记为 **product_match**。

输出：
  * `data\rules_provenance_ord.json`
  * `reports\第七十五轮-规则来源体检（ORD实测）.md`

口径与限制写在报告里。**不打分、不排序**，只给可复核的计数与样例。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from itertools import product
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
RULE_PATH = STAGE / "rules" / "rules.json"
INDEX_PATH = STAGE / "data" / "ord_reaction_index.jsonl"
PAPER_PATH = Path(r"D:\TCMAI\docs\supplementary\TableS1_reaction_rules.csv")
OUT_JSON = STAGE / "data" / "rules_provenance_ord.json"
OUT_MD = STAGE / "reports" / "第七十五轮-规则来源体检（ORD实测）.md"


def canon_plain(mol) -> str:
    """去映射号 / 显式 H / 立体，返回规范 SMILES；失败返回空串。"""
    if mol is None:
        return ""
    try:
        m = Chem.Mol(mol)
    except Exception:
        return ""
    try:
        m = Chem.RemoveHs(m, sanitize=False)
    except Exception:
        pass
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


def canons_of(mol) -> set[str]:
    """整分子 + 各片段都算候选（ORD 把盐/多产物分开存）。"""
    out: set[str] = set()
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


def count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024 * 8)
            if not chunk:
                break
            n += chunk.count(b"\n")
    return n


def paper_tiers() -> dict[str, str]:
    """规则名 -> same / changed；论文里没有的记为 new。"""
    import csv

    out: dict[str, str] = {}
    if not PAPER_PATH.exists():
        return out
    with PAPER_PATH.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            out[row["规则名"].strip()] = row["SMARTS"].strip()
    return out


def load_rules() -> list[dict]:
    d = json.loads(RULE_PATH.read_text(encoding="utf-8"))
    return d if isinstance(d, list) else d.get("rules") or []


def build_rule_objs(rules: list[dict]) -> list[dict]:
    out = []
    for r in rules:
        try:
            rxn = AllChem.ReactionFromSmarts(str(r.get("smarts") or ""))
        except Exception as exc:  # noqa: BLE001
            rxn = None
            err = str(exc)[:160]
        else:
            err = ""
        out.append({
            "rule": r,
            "rxn": rxn,
            "n_templates": rxn.GetNumReactantTemplates() if rxn is not None else 0,
            "parse_error": err,
            "templates": ([rxn.GetReactantTemplate(i)
                           for i in range(rxn.GetNumReactantTemplates())]
                          if rxn is not None else []),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60000,
                    help="抽样记录数（默认 60000；0=全量）")
    ap.add_argument("--only", default="",
                    help="只跑这些规则 id（逗号分隔；默认全部）")
    ap.add_argument("--conditions", action="store_true",
                    help="同时收集每条规则所有 product_match 记录的 ORD 条件")
    ap.add_argument("--out-json", default=str(OUT_JSON))
    ap.add_argument("--out-md", default=str(OUT_MD))
    args = ap.parse_args()

    rules = load_rules()
    if args.only:
        keep = {x.strip() for x in args.only.split(",") if x.strip()}
        rules = [r for r in rules if r.get("id") in keep]
        if not rules:
            print("--only 没有匹配到任何规则")
            return 2
    robjs = build_rule_objs(rules)
    paper = paper_tiers()

    total = count_lines(INDEX_PATH)
    limit = args.limit if args.limit > 0 else total
    stride = max(1, total // max(1, limit))

    print(f"ORD 索引 {total:,} 行；目标抽样 {min(limit, total):,} 条；步长 {stride}")
    print(f"规则 {len(rules)} 条（单模板 "
          f"{sum(1 for x in robjs if x['n_templates'] == 1)}，双模板 "
          f"{sum(1 for x in robjs if x['n_templates'] == 2)}）")

    stats = {
        "records": 0,
        "parse_fail": 0,
        "product_parse_fail": 0,
        "empty_reactants": 0,
        "rules": {},
    }
    for x in robjs:
        rid = x["rule"].get("id")
        stats["rules"][rid] = {
            "fired": 0,
            "product_match": 0,
            "run_errors": 0,
            "invalid_products": 0,
            "examples_match": [],
            "examples_fired": [],
            "mismatch_example": None,
            "conditions": {
                "n_match": 0, "n_temp": 0, "n_catalyst": 0,
                "n_solvent": 0, "n_reagent": 0, "n_any": 0,
                "temps": Counter(), "catalysts": Counter(),
                "solvents": Counter(), "reagents": Counter(),
                "examples": [],
            },
        }

    t0 = time.time()
    kept = 0
    with INDEX_PATH.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh):
            if lineno % stride:
                continue
            if kept >= limit:
                break
            kept += 1
            try:
                rec = json.loads(line)
            except Exception:
                stats["parse_fail"] += 1
                continue
            reactants = rec.get("reactants") or []
            if not reactants:
                stats["empty_reactants"] += 1
                continue
            mols = []
            for smi in reactants:
                m = Chem.MolFromSmiles(smi)
                if m is None:
                    stats["parse_fail"] += 1
                    continue
                mols.append(m)
            if not mols:
                continue

            actual: set[str] = set()
            for smi in rec.get("products") or []:
                pm = Chem.MolFromSmiles(smi)
                if pm is None:
                    stats["product_parse_fail"] += 1
                    continue
                actual |= canons_of(pm)
            if not actual:
                continue

            stats["records"] += 1
            for x in robjs:
                rid = x["rule"].get("id")
                st = stats["rules"][rid]
                rxn = x["rxn"]
                if rxn is None:
                    st["run_errors"] += 1
                    continue
                templates = x["templates"]
                # 先做便宜的 substructure 预筛，避免盲跑全部组合。
                hits = []
                for tpl in templates:
                    hits.append([i for i, m in enumerate(mols)
                                 if m.HasSubstructMatch(tpl)])
                if any(not h for h in hits):
                    continue

                fired_here = False
                matched_here = False
                gen_str = ""
                for idxs in product(*[range(len(mols)) for _ in templates]):
                    if any(i not in hits[k] for k, i in enumerate(idxs)):
                        continue
                    try:
                        prods = rxn.RunReactants(tuple(mols[i] for i in idxs))
                    except Exception:
                        st["run_errors"] += 1
                        continue
                    for prod_tuple in prods:
                        for pmol in prod_tuple:
                            cs = canons_of(pmol)
                            if not cs:
                                st["invalid_products"] += 1
                                continue
                            fired_here = True
                            if not gen_str:
                                gen_str = sorted(cs)[0]
                            if cs & actual:
                                matched_here = True
                                if len(st["examples_match"]) < 3:
                                    st["examples_match"].append({
                                        "rid": rec.get("rid"),
                                        "reactants": reactants[:4],
                                        "generated": sorted(cs & actual),
                                        "actual": sorted(actual)[:6],
                                    })
                        if matched_here:
                            break
                    if matched_here:
                        break
                    if fired_here and st["mismatch_example"] is None:
                        st["mismatch_example"] = {
                            "rid": rec.get("rid"),
                            "reactants": reactants[:4],
                            "generated": gen_str,
                            "actual": sorted(actual)[:6],
                        }

                if fired_here:
                    st["fired"] += 1
                    if len(st["examples_fired"]) < 2:
                        st["examples_fired"].append({
                            "rid": rec.get("rid"),
                            "reactants": reactants[:4],
                            "generated": gen_str,
                            "actual": sorted(actual)[:6],
                        })
                if matched_here:
                    st["product_match"] += 1
                    if args.conditions:
                        cc = st["conditions"]
                        temp = str(rec.get("temp") or "")
                        cats = rec.get("catalysts") or []
                        sols = rec.get("solvents") or []
                        reags = rec.get("reagents") or []
                        cc["n_match"] += 1
                        if temp:
                            cc["n_temp"] += 1
                            cc["temps"][temp] += 1
                        if cats:
                            cc["n_catalyst"] += 1
                            for x in cats:
                                cc["catalysts"][x] += 1
                        if sols:
                            cc["n_solvent"] += 1
                            for x in sols:
                                cc["solvents"][x] += 1
                        if reags:
                            cc["n_reagent"] += 1
                            for x in reags:
                                cc["reagents"][x] += 1
                        if temp or cats or sols or reags:
                            cc["n_any"] += 1
                        if len(cc["examples"]) < 5:
                            cc["examples"].append({
                                "rid": rec.get("rid"),
                                "temp": temp,
                                "catalysts": cats,
                                "solvents": sols,
                                "reagents": reags,
                            })

            if kept % 5000 == 0:
                el = time.time() - t0
                print(f"  ... {kept:,}/{limit:,} 条（{el:.0f}s）")

    elapsed = time.time() - t0
    print(f"完成：扫描 {stats['records']:,} 条，用时 {elapsed:.0f}s")

    # 组装输出（按 rules.json 原顺序，不排序）
    rows = []
    for x in robjs:
        r = x["rule"]
        rid = r.get("id")
        st = stats["rules"][rid]
        if r.get("name") in paper:
            tier = "论文原样" if str(r.get("smarts", "")).strip() == paper[r["name"]] else "论文修正"
        else:
            tier = "自写新增"
        cond = st["conditions"]
        cond_out = None
        if args.conditions:
            cond_out = {
                "n_match": cond["n_match"],
                "n_temp": cond["n_temp"],
                "n_catalyst": cond["n_catalyst"],
                "n_solvent": cond["n_solvent"],
                "n_reagent": cond["n_reagent"],
                "n_any": cond["n_any"],
                "temps": dict(cond["temps"].most_common(20)),
                "catalysts": dict(cond["catalysts"].most_common(20)),
                "solvents": dict(cond["solvents"].most_common(20)),
                "reagents": dict(cond["reagents"].most_common(20)),
                "examples": cond["examples"],
            }
        rows.append({
            "id": rid,
            "name": r.get("name"),
            "category": r.get("category"),
            "status": r.get("status"),
            "paper_tier": tier,
            "smarts": r.get("smarts"),
            "n_templates": x["n_templates"],
            "fired": st["fired"],
            "product_match": st["product_match"],
            "run_errors": st["run_errors"],
            "invalid_products": st["invalid_products"],
            "examples_match": st["examples_match"],
            "examples_fired": st["examples_fired"],
            "mismatch_example": st["mismatch_example"],
            "conditions": cond_out,
        })

    out = {
        "sample": {
            "index": str(INDEX_PATH),
            "total_lines": total,
            "requested": limit,
            "stride": stride,
            "scanned_records": stats["records"],
            "elapsed_sec": round(elapsed, 1),
        },
        "parse_fail": stats["parse_fail"],
        "product_parse_fail": stats["product_parse_fail"],
        "empty_reactants": stats["empty_reactants"],
        "rows": rows,
    }
    Path(args.out_json).write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    n_match = sum(1 for r in rows if r["product_match"] > 0)
    n_fired = sum(1 for r in rows if r["fired"] > 0)
    by_tier = Counter(r["paper_tier"] for r in rows)

    with Path(args.out_md).open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 规则来源体检（ORD 真实反应实测）\n\n")
        f.write("> **做法**：把每条规则的 SMARTS 套到 ORD 真实记录的**反应物**上，"
                "生成产物经「去映射号 / 去显式 H / 去立体 / 拆片段」规范化，"
                "再与记录的真实产物比对。\n")
        f.write("> **product_match** = 生成片段与该记录真实产物有交集；"
                "**fired** = 规则至少生成过一个可解析产物。\n\n")
        f.write("## 口径（先看这段）\n\n")
        f.write(f"* 数据源：`{INDEX_PATH}`，共 {total:,} 行；"
                f"按步长 {stride} 等距抽样，实际扫描 **{stats['records']:,}** 条。\n")
        f.write("* 这是**前向试跑**，不是逆合成审计；ORD 记录未必是同一反应类型，"
                "所以 `fired` 多不代表规则对，只代表底物里存在可匹配子结构。\n")
        f.write("* 规则里的水/共试剂多为**隐含**（如水解规则不把 H2O 写成反应物），"
                "因此本审计只把规则套到记录的反应物列；这比方案 a 的模板签名更接近真实用法。\n")
        f.write("* 规范化忽略立体与显式 H；`product_match` 是**分子图相同**，"
                "不是条件/机理相同。\n")
        f.write("* 只给计数与样例，**不打分、不排序**；`rules.json` 原顺序。\n\n")
        f.write("## 总览\n\n")
        f.write(f"* 规则：**{len(rows)}** 条（{dict(by_tier)}）\n")
        f.write(f"* 至少 `fired` 一次：**{n_fired}** 条\n")
        f.write(f"* 至少 `product_match` 一次：**{n_match}** 条\n")
        f.write(f"* 反应物解析失败：**{stats['parse_fail']}** 次；"
                f"产物解析失败：**{stats['product_parse_fail']}** 次\n\n")
        if args.conditions:
            f.write("### 条件覆盖（所有 product_match 记录）\n\n")
            f.write("| 规则 | 命中记录 | 温度 | 催化剂 | 溶剂 | 试剂 | 任一条件 |\n")
            f.write("|---|---:|---:|---:|---:|---:|---:|\n")
            for r in rows:
                c = r.get("conditions") or {}
                if not c or not c.get("n_match"):
                    continue
                f.write("| `%s` %s | %d | %d | %d | %d | %d | %d |\n"
                        % (r["id"], r["name"], c["n_match"], c["n_temp"],
                           c["n_catalyst"], c["n_solvent"], c["n_reagent"],
                           c["n_any"]))
            f.write("\n")
        f.write("## 逐条结果\n\n")
        f.write("| # | 规则 | 类别 | 状态 | 论文档位 | fired | product_match | "
                "run_errors | 首个命中 rid |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(rows, 1):
            rid = r["examples_match"][0]["rid"] if r["examples_match"] else "—"
            f.write(f"| {i} | `{r['id']}` {r['name']} | {r['category']} | "
                    f"{r['status']} | {r['paper_tier']} | {r['fired']} | "
                    f"{r['product_match']} | {r['run_errors']} | {rid} |\n")
        f.write("\n## 命中样例（前 3 条）\n\n")
        for r in rows:
            if not r["examples_match"]:
                continue
            f.write(f"### `{r['id']}` {r['name']}\n\n")
            for ex in r["examples_match"]:
                f.write(f"* `{ex['rid']}`\n")
                f.write(f"  * 反应物：`{' + '.join(ex['reactants'])}`\n")
                f.write(f"  * 生成命中：`{' ; '.join(ex['generated'])}`\n")
                f.write(f"  * 记录产物：`{' ; '.join(ex['actual'])}`\n")
            f.write("\n")
        f.write("## 失败/无命中说明\n\n")
        f.write("* 没有 `product_match` 的规则不等于“规则错”：可能是 ORD 抽样里没有该反应类型、"
                "底物取代基不匹配、规则要求多步/共试剂，或记录方向相反。\n")
        f.write("* `run_errors` 是 RDKit 在具体底物上抛错的次数，已逐条累计；"
                "`invalid_products` 是生成物无法规范化的次数。\n")
        f.write("* 需要外部权威规则来源时，下一步应查论文/数据集原文；"
                "本报告只回答“有没有在 ORD 真实记录里跑出相同产物”。\n")

    print(f"  -> {args.out_json}")
    print(f"  -> {args.out_md}")
    print(f"  至少 fired：{n_fired}/{len(rows)}；至少 product_match：{n_match}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
