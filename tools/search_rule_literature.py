# -*- coding: utf-8 -*-
r"""B：6 条零命中规则的外部文献检索（OpenAlex，只读）。

不是“问 AI 自证”：只抓公开文献元数据/摘要，保留 DOI、年份、期刊、摘要片段。
输出：
  data\rule_literature_search.json
  reports\第七十五轮-规则外部文献检索.md
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
OUTJ = STAGE / "data" / "rule_literature_search.json"
OUTM = STAGE / "reports" / "第七十五轮-规则外部文献检索.md"

QUERIES = {
    "hydrolysis_hemiacetal_001": [
        "hydrolysis of hemiacetals kinetics acid",
        "acid catalyzed hydrolysis of acetals hemiacetal intermediate",
    ],
    "oxidation_phenol_quinone_001": [
        "oxidation of catechol to ortho-quinone periodate",
        "tyrosinase catechol oxidation quinone",
    ],
    "hydration_enone_001": [
        "acid catalyzed hydration of alpha beta unsaturated ketones",
        "Michael addition of water to enones",
    ],
    "condensation_hemiacetal_001": [
        "kinetics of hemiacetal formation aldehyde alcohol",
        "hemiacetal equilibrium aqueous solution aldehyde",
    ],
    "addition_thiohemiacetal_001": [
        "thiohemiacetal formation aldehyde thiol",
        "S-hemiacetal thiol addition aldehyde",
    ],
    "decarboxylation_cinnamic_001": [
        "decarboxylation of cinnamic acid copper quinoline",
        "thermal decarboxylation cinnamic acid styrene",
    ],
}


def abstract_of(w: dict) -> str:
    inv = w.get("abstract_inverted_index") or {}
    pos = {}
    for word, ids in inv.items():
        for i in ids:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def search(q: str, n: int = 5) -> dict:
    r = requests.get(
        "https://api.openalex.org/works",
        params={
            "search": q, "per-page": n,
            "select": "id,doi,title,publication_year,primary_location,"
                      "abstract_inverted_index,cited_by_count,type",
        },
        timeout=30,
    )
    if r.status_code != 200:
        return {"query": q, "http": r.status_code, "error": r.text[:300],
                "results": []}
    out = []
    for w in r.json().get("results", []):
        pl = w.get("primary_location") or {}
        src = (pl.get("source") or {}).get("display_name") or ""
        out.append({
            "doi": w.get("doi") or "",
            "title": w.get("title") or "",
            "year": w.get("publication_year"),
            "journal": src,
            "type": w.get("type"),
            "cited_by": w.get("cited_by_count"),
            "abstract": abstract_of(w)[:1200],
        })
    return {"query": q, "http": 200, "results": out}


def main() -> int:
    all_out = {}
    errors = 0
    for rid, qs in QUERIES.items():
        rows = []
        for q in qs:
            res = search(q)
            if res["http"] != 200:
                errors += 1
            rows.append(res)
            print("%-32s %-55s HTTP %s / %d"
                  % (rid, q[:55], res["http"], len(res["results"])))
            time.sleep(0.7)
        all_out[rid] = rows
    OUTJ.write_text(json.dumps(all_out, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 6 条零命中规则的外部文献检索\n\n")
        f.write("> 来源：OpenAlex 公开文献元数据/摘要（不是 AI 生成）；"
                "DOI/标题/年份/期刊均保留。\n")
        f.write("> 这是**检索结果**，不是最终结论；下一步要逐条读摘要/原文，"
                "确认反应条件与底物是否匹配。\n\n")
        for rid, rows in all_out.items():
            f.write("## `%s`\n\n" % rid)
            for res in rows:
                f.write("### 查询：`%s`\n\n" % res["query"])
                if res["http"] != 200:
                    f.write("HTTP %s：`%s`\n\n"
                            % (res["http"], res.get("error", "")[:300]))
                    continue
                for i, w in enumerate(res["results"], 1):
                    f.write("%d. **%s**（%s）\n" % (i, w["title"], w["year"]))
                    f.write("   * DOI：%s\n" % (w["doi"] or "—"))
                    f.write("   * 期刊：%s；引用：%s\n"
                            % (w["journal"] or "—", w["cited_by"]))
                    if w["abstract"]:
                        f.write("   * 摘要片段：%s\n" % w["abstract"][:500])
                    f.write("\n")
        f.write("\n## 统计\n\n")
        f.write("* 规则：%d；查询：%d；HTTP 失败：%d\n"
                % (len(all_out), sum(len(v) for v in all_out.values()), errors))

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  查询 %d 次，HTTP 失败 %d"
          % (sum(len(v) for v in all_out.values()), errors))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
