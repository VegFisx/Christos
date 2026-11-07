# -*- coding: utf-8 -*-
r"""规则-条件窗口（v1）：从规则体检的 ORD 样例记录汇总条件。

输入：
  data\rules_provenance_ord.json
  data\rule_condition_examples.json
输出：
  data\rule_condition_window.json
  reports\第七十五轮-规则条件窗口.md

口径：每条规则最多用体检时保留的 3 条命中样例；**不是全量匹配记录**。
温度保留原值/原始数值范围；催化剂、溶剂去重列示；试剂字段当前源数据为空。
不打分、不排序；行序 = rules.json 原顺序。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
PROV = STAGE / "data" / "rules_provenance_ord.json"
COND = STAGE / "data" / "rule_condition_examples.json"
OUTJ = STAGE / "data" / "rule_condition_window.json"
OUTM = STAGE / "reports" / "第七十五轮-规则条件窗口.md"


def temp_num(s: str):
    parts = str(s or "").split()
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


def uniq(xs) -> list:
    out = []
    for x in xs:
        if x and x not in out:
            out.append(x)
    return out


def main() -> int:
    d = json.loads(PROV.read_text(encoding="utf-8"))
    rows = d["rows"]
    found = json.loads(COND.read_text(encoding="utf-8")).get("found", {})
    has_full = any((r.get("conditions") or {}).get("n_match") for r in rows)

    out_rows = []
    for r in rows:
        if r.get("product_match", 0) <= 0:
            continue
        cond = r.get("conditions") or {}
        if cond.get("n_match"):
            n_examples = cond["n_match"]
            rids = [ex.get("rid") for ex in (cond.get("examples") or [])
                    if ex.get("rid")]
            temps_raw = list((cond.get("temps") or {}).keys())
            cats = list((cond.get("catalysts") or {}).keys())
            sols = list((cond.get("solvents") or {}).keys())
            reags = list((cond.get("reagents") or {}).keys())
            n_any = cond.get("n_any", 0)
            n_temp = cond.get("n_temp", 0)
            n_cat = cond.get("n_catalyst", 0)
            n_sol = cond.get("n_solvent", 0)
            n_reag = cond.get("n_reagent", 0)
        else:
            rids = [ex.get("rid") for ex in (r.get("examples_match") or [])
                    if ex.get("rid")]
            recs = [found[x] for x in rids if x in found]
            n_examples = len(recs)
            temps_raw = uniq([rec.get("temp") for rec in recs])
            cats = uniq([c for rec in recs for c in (rec.get("catalysts") or [])])
            sols = uniq([s for rec in recs for s in (rec.get("solvents") or [])])
            reags = uniq([x for rec in recs for x in (rec.get("reagents") or [])])
            n_any = sum(1 for rec in recs
                        if rec.get("temp") or rec.get("catalysts")
                        or rec.get("reagents") or rec.get("solvents"))
            n_temp = sum(1 for rec in recs if rec.get("temp"))
            n_cat = sum(1 for rec in recs if rec.get("catalysts"))
            n_sol = sum(1 for rec in recs if rec.get("solvents"))
            n_reag = sum(1 for rec in recs if rec.get("reagents"))
        temps_num = [temp_num(x) for x in temps_raw]
        temps_num = [x for x in temps_num if x is not None]
        out_rows.append({
            "id": r["id"], "name": r.get("name"), "paper_tier": r.get("paper_tier"),
            "status": r.get("status"), "product_match": r.get("product_match"),
            "condition_scope": "full" if cond.get("n_match") else "sample",
            "example_rids": rids, "n_examples": n_examples,
            "n_with_any_condition": n_any,
            "n_with_temp": n_temp,
            "n_with_catalyst": n_cat,
            "n_with_solvent": n_sol,
            "n_with_reagent": n_reag,
            "temps_raw": temps_raw,
            "temps_min": min(temps_num) if temps_num else None,
            "temps_max": max(temps_num) if temps_num else None,
            "catalysts": cats, "solvents": sols, "reagents": reags,
        })

    OUTJ.write_text(json.dumps({
        "scope": ("全部 product_match 记录（audit --conditions）" if has_full
                  else "每条规则最多 3 条 ORD 命中样例（examples_match）"),
        "rows": out_rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    n_rules = len(out_rows)
    n_temp = sum(1 for x in out_rows if x["n_with_temp"])
    n_cat = sum(1 for x in out_rows if x["n_with_catalyst"])
    n_sol = sum(1 for x in out_rows if x["n_with_solvent"])
    n_any = sum(1 for x in out_rows if x["n_with_any_condition"])
    n_none = n_rules - n_any
    n_reag = sum(1 for x in out_rows if x["n_with_reagent"])
    by_tier = Counter(x["paper_tier"] for x in out_rows)

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 规则条件窗口（%s）\n\n"
                % ("v2，全量命中记录" if has_full else "v1，样例级"))
        f.write("> 对象：`rules_provenance_ord.json` 里 `product_match > 0` 的规则。\n")
        if has_full:
            f.write("> 数据：每条规则的**全部 product_match 记录**"
                    "（`--conditions` 收集）；温度/催化剂/溶剂为记录原值。\n")
        else:
            f.write("> 数据：每条规则最多 3 条 ORD 命中样例"
                    "（体检时保留的 `examples_match`）；**不是全量匹配记录**。\n")
        f.write("> 条件字段原样取自 `ord_reaction_index.jsonl`；"
                "空 = 该样例没有该字段。不打分、不排序。\n\n")
        f.write("## 总览\n\n")
        f.write("* 有 ORD 产物命中的规则：**%d** 条（%s）\n"
                % (n_rules, dict(by_tier)))
        rec_label = "命中记录" if has_full else "样例"
        f.write("* 至少一条%s带条件：**%d / %d**；完全没有条件字段：**%d**\n"
                % (rec_label, n_any, n_rules, n_none))
        f.write("* 至少一条%s带温度：%d；催化剂：%d；溶剂：%d；试剂：%d\n\n"
                % (rec_label, n_temp, n_cat, n_sol, n_reag))
        f.write("> ⚠ 试剂字段仍为 0：ORD 源数据很少把试剂标成 REAGENT"
                "（前 2,000 条探针：REAGENT 0），不是本脚本漏算。\n\n")

        f.write("## 逐条条件窗口\n\n")
        f.write("| # | 规则 | 论文档位 | %s | 带条件 | 温度原值 | "
                "催化剂（去重） | 溶剂（去重） | 首个%s |\n"
                % ("命中记录" if has_full else "样例数",
                   "记录" if has_full else "样例"))
        f.write("|---|---|---|---:|---:|---|---|---|---|\n")
        for i, x in enumerate(out_rows, 1):
            temps = " / ".join(x["temps_raw"]) or "—"
            cats = "、".join(x["catalysts"][:4]) or "—"
            sols = "、".join(x["solvents"][:5]) or "—"
            first = x["example_rids"][0] if x["example_rids"] else "—"
            f.write("| %d | `%s` %s | %s | %d | %d | %s | %s | %s | `%s` |\n"
                    % (i, x["id"], x.get("name") or "", x.get("paper_tier") or "?",
                       x["n_examples"], x["n_with_any_condition"], temps, cats, sols,
                       first))

        f.write("\n## 没有任何条件字段的规则\n\n")
        none_rows = [x for x in out_rows if x["n_with_any_condition"] == 0]
        if not none_rows:
            f.write("（没有；所有命中规则至少有一条样例带条件字段。）\n")
        else:
            for x in none_rows:
                f.write("* `%s` %s（%s；%s %d 条）\n"
                        % (x["id"], x.get("name") or "", x.get("paper_tier") or "?",
                           "命中记录" if has_full else "样例",
                           x["n_examples"]))

        f.write("\n## 读法\n\n")
        if has_full:
            f.write("* 这是**全量 product_match 记录**的条件覆盖；"
                    "温度/催化剂/溶剂是记录原值，不是统计显著的最优条件。\n")
        else:
            f.write("* 这是**样例级**窗口，不是统计显著的温度分布；"
                    "要得到全量分布，需要对 60k 抽样里所有命中记录重新收集条件。\n")
        f.write("* 温度原值里的第二个数是 ORD 的单位码（常见 `1`）；"
                "本表不做单位换算，避免误标 °C/K。\n")
        f.write("* 催化剂/溶剂是记录里出现过的原值，不代表最优条件，也不代表缺了就不能反应。\n")
        f.write("* 机器可读：`data/rule_condition_window.json`。\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  规则 %d ｜ 有任一条件 %d ｜ 无条件 %d ｜ 温度 %d ｜ 催化剂 %d ｜ 溶剂 %d"
          % (n_rules, n_any, n_none, n_temp, n_cat, n_sol))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
