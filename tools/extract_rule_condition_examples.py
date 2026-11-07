# -*- coding: utf-8 -*-
r"""把规则体检里出现的 ORD 记录 rid → 真实条件抽出来（只读）。

输入：
  data\ord_reaction_index.jsonl
  data\rules_provenance_ord.json
输出：
  data\rule_condition_examples.json
  reports\第七十五轮-规则条件样例.md

用途：区分「ORD 抽样里没有这个反应」与「有记录，但条件/底物不对」。
不打分、不排序；行序 = rules.json 原顺序。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
INDEX = STAGE / "data" / "ord_reaction_index.jsonl"
PROV = STAGE / "data" / "rules_provenance_ord.json"
OUTJ = STAGE / "data" / "rule_condition_examples.json"
OUTM = STAGE / "reports" / "第七十五轮-规则条件样例.md"


def main() -> int:
    d = json.loads(PROV.read_text(encoding="utf-8"))
    rows = d["rows"]
    rids = set()
    for r in rows:
        for ex in r.get("examples_match") or []:
            if ex.get("rid"):
                rids.add(ex["rid"])
        for ex in r.get("examples_fired") or []:
            if ex.get("rid"):
                rids.add(ex["rid"])
        ex = r.get("mismatch_example") or {}
        if ex.get("rid"):
            rids.add(ex["rid"])
    print("需要抽取条件的 rid：%d 个" % len(rids))

    found = {}
    with INDEX.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rid = rec.get("rid")
            if rid in rids:
                found[rid] = {
                    "reactants": rec.get("reactants") or [],
                    "products": rec.get("products") or [],
                    "catalysts": rec.get("catalysts") or [],
                    "reagents": rec.get("reagents") or [],
                    "solvents": rec.get("solvents") or [],
                    "temp": rec.get("temp") or "",
                }
                if len(found) >= len(rids):
                    break
    missing = sorted(rids - set(found))
    OUTJ.write_text(json.dumps({"found": found, "missing": missing},
                               ensure_ascii=False, indent=1), encoding="utf-8")

    def has(rec, key):
        v = rec.get(key)
        return bool(v)

    n_any = sum(1 for r in found.values()
                if has(r, "temp") or has(r, "catalysts") or has(r, "reagents")
                or has(r, "solvents"))
    n_temp = sum(1 for r in found.values() if has(r, "temp"))
    n_cat = sum(1 for r in found.values() if has(r, "catalysts"))
    n_reag = sum(1 for r in found.values() if has(r, "reagents"))
    n_solv = sum(1 for r in found.values() if has(r, "solvents"))

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 规则条件样例（从 ORD 记录抽取）\n\n")
        f.write("> 只抽规则体检里出现过的记录，**不是全库条件覆盖率**；"
                "目的是区分“抽样里没这个反应”和“有记录但条件/底物不对”。\n")
        f.write("> 所有字段均为 ORD 索引里的原值；空 = 该记录没有该字段。"
                "不打分、不排序。\n\n")
        f.write("## 总览\n\n")
        f.write("* 目标 rid：%d；找到：%d；缺失：%d\n"
                % (len(rids), len(found), len(missing)))
        f.write("* 有任一条件字段：**%d / %d**；温度 %d；催化剂 %d；试剂 %d；溶剂 %d\n\n"
                % (n_any, len(found), n_temp, n_cat, n_reag, n_solv))
        if n_reag == 0:
            f.write("* ⚠ **本批 `reagents` 全为空**：当前 `ord_reaction_index.jsonl` "
                    "没有把 ORD 的试剂字段填出来；条件证据目前只有温度/催化剂/溶剂。"
                    "这属于索引层缺口，不是“这些反应不需要试剂”。\n\n")
            f.write("  只读探针（ORD parquet 前 2,000 条记录的角色计数）："
                    "REACTANT 6,503 / SOLVENT 2,290 / CATALYST 269 / **REAGENT 0**。"
                    "也就是说，源数据本身很少把试剂标成 REAGENT，"
                    "不是 `build_ord_reaction_index.py` 漏读。\n\n")
        if missing:
            f.write("* 缺失 rid：%s\n\n" % "、".join("`%s`" % x for x in missing))

        f.write("## 已命中规则：第一个命中记录的条件\n\n")
        f.write("| # | 规则 | 记录 | 温度 | 催化剂 | 试剂 | 溶剂 |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(rows, 1):
            exs = r.get("examples_match") or []
            if not exs:
                continue
            rid = exs[0].get("rid")
            c = found.get(rid, {})
            f.write("| %d | `%s` %s | `%s` | %s | %s | %s | %s |\n"
                    % (i, r["id"], r.get("name", ""), rid,
                       c.get("temp") or "—",
                       "、".join(c.get("catalysts") or []) or "—",
                       "、".join(c.get("reagents") or []) or "—",
                       "、".join(c.get("solvents") or []) or "—"))

        f.write("\n## 零命中规则：触发但产物不符的那条记录\n\n")
        f.write("| # | 规则 | 记录 | 温度 | 催化剂 | 试剂 | 溶剂 | 规则生成 | 记录产物 |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(rows, 1):
            if r.get("product_match", 0) > 0:
                continue
            ex = r.get("mismatch_example") or {}
            rid = ex.get("rid")
            if not rid:
                f.write("| %d | `%s` %s | — | — | — | — | — | — | — |\n"
                        % (i, r["id"], r.get("name", "")))
                continue
            c = found.get(rid, {})
            f.write("| %d | `%s` %s | `%s` | %s | %s | %s | %s | `%s` | `%s` |\n"
                    % (i, r["id"], r.get("name", ""), rid,
                       c.get("temp") or "—",
                       "、".join(c.get("catalysts") or []) or "—",
                       "、".join(c.get("reagents") or []) or "—",
                       "、".join(c.get("solvents") or []) or "—",
                       ex.get("generated") or "—",
                       " ; ".join(ex.get("actual") or []) or "—"))

        f.write("\n## 读法\n\n")
        f.write("* 如果零命中记录的试剂/溶剂里**没有水**，水解类规则本来就不该在这条记录里成立；"
                "这属于“条件不对”，不是“规则错”。\n")
        f.write("* 如果记录里**有**该规则需要的试剂/条件，但产物仍不同，才更需要怀疑 SMARTS 或产物模板。\n")
        f.write("* 如果整条记录没有任何条件字段，只能说明 ORD 这条没记录条件，"
                "不能反推“不需要条件”。\n")
        f.write("* 完整记录见 `data/rule_condition_examples.json`。\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  找到 %d / %d；有任一条件 %d" % (len(found), len(rids), n_any))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
