# -*- coding: utf-8 -*-
"""把 2026-11-06 联网核查的文献证据落库。

做两件事：
1. 新增 rules/literature_evidence.json —— 非炮制类文献证据表（DOI + 原句）。
2. 往 rules/rules.json 追加 cleavage_cyanohydrin_001（氰醇裂解），
   provenance=cited，evidence_id 指向新表。

只新增、不改动既有 70 条规则的内容；重复执行是幂等的。
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

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
EVID = ROOT / "rules" / "literature_evidence.json"

EVIDENCE = {
    "schema_version": "chemreact-literature-evidence/1",
    "generated_at": "2026-11-06",
    "note": ("每条都必须有 DOI/URL 与原文引句；找不到就留空并写 status=not_found。"
             "本表只服务 rules/rules.json 的 provenance=cited 规则。"),
    "entries": [
        {
            "id": "lit_cyanohydrin_haisman1967",
            "claim": "苦杏仁苷三步酶解：苦杏仁苷→野樱苷+葡萄糖→扁桃腈+葡萄糖→苯甲醛+HCN",
            "reaction": "氰醇（羟腈）裂解：R-CH(OH)-C#N -> R-CHO + HCN",
            "sources": [{
                "title": "The elimination of cyanide from mandelonitrile and the hydrolysis of amygdalin",
                "journal": "Biochemical Journal",
                "year": 1967,
                "doi": "10.1042/bj1030528",
                "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC1270437/",
                "quote": ("amygdalin was hydrolysed to prunasin and glucose; prunasin to "
                          "mandelonitrile and glucose; mandelonitrile to benzaldehyde and "
                          "hydrocyanic acid"),
                "type": "primary",
            }],
            "conditions": {"temperature_C": None, "time_min": None, "pH": None,
                           "note": "酶法体外实验，摘要未给温时 pH；另有 Foods 2024;13(3):437 "
                                   "(10.3390/foods13030437) 给苯甲醛生成 53 °C/pH 5.8/1.8 h"},
            "usage": "支持 cleavage_cyanohydrin_001；该规则同时是苦杏仁/麻黄汤里"
                     "「扁桃腈→苯甲醛」缺失环节的来源。",
            "weakness": "酶催化证据，非纯热化学；温度/时间未标定，因此不参与条件门控。",
        },
        {
            "id": "lit_hemiketal_paeoniflorigenone_1983",
            "claim": "芍药苷（笼状半缩酮）的苷元以开链酮式存在（paeoniflorigenone）",
            "reaction": "半缩酮 -> 开链酮（异构化）",
            "sources": [{
                "title": "Paeoniflorigenone, a novel monoterpene from Paeoniae Radix",
                "journal": "Chemical & Pharmaceutical Bulletin",
                "year": 1983,
                "doi": "10.1248/cpb.31.577",
                "quote": "isolated from the roots of Paeonia albiflora",
                "type": "primary_structure_only",
            }],
            "conditions": {"temperature_C": None, "time_min": None, "pH": None},
            "usage": ("只作结构证据：证明酮式苷元真实存在。"
                      "**没有反应级文献，因此不建规则**（按 AGENTS §十二）。"),
            "weakness": "无转化描述、无条件；不能拿来当判据。",
        },
        {
            "id": "lit_vinegar_esterification_jwcmm2025",
            "claim": "醋制促进二萜结构转化，包含醚键水解、内酯开环、酯化、氧化、环氧开环",
            "reaction": "有机酸+醇->酯（炮制语境）",
            "sources": [{
                "title": "醋制狼毒类药材化学成分及药理作用研究进展",
                "journal": "中国中药杂志",
                "year": 2025,
                "doi": "10.19540/j.cnki.cjcmm.20250526.301",
                "quote": ("vinegar processing promotes structural transformations of "
                          "diterpenoids, including ... esterification"),
                "type": "review",
            }],
            "conditions": {"temperature_C": None, "time_min": None, "pH": None},
            "usage": ("只支持「醋炙下可能发生酯化」这一方向性说法；"
                      "无底物、无产物、无条件，所以不新增规则。"),
            "weakness": "综述二手，且与「醋酸与生物碱成盐」机制并存（Wu 2021, "
                        "10.1155/2021/1271953）。",
        },
    ],
}

CYANO_RULE = {
    "id": "cleavage_cyanohydrin_001",
    "name": "氰醇裂解（羟腈→醛+氰化氢）",
    "category": "cleavage",
    "smarts": "[C;H1:1]([OH1:2])([CX2#N:3])[#6:4]>>[CH1:1](=[O:2])[#6:4].[C:3]#N",
    "reversible": False,
    "co_reagents": {},
    "byproducts": {"HCN": 1},
    "condition_profile": "hydrolysis",
    "priority": 0.8,
    "status": "active",
    "notes": ("文献：Haisman & Knight, Biochem J 1967;103(2):528 "
              "(10.1042/bj1030528) —— 扁桃腈自发/酶促裂解为苯甲醛 + HCN。"
              "补的是「苦杏仁苷→野樱苷→扁桃腈→苯甲醛」链的最后一环；"
              "温度/时间未标定，故不参与任何 extent 门控。"),
    "max_products_per_molecule": 3,
    "thermo_unreliable": True,
    "provenance": "cited",
    "evidence_id": "lit_cyanohydrin_haisman1967",
}


def main() -> int:
    EVID.write_text(json.dumps(EVIDENCE, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出", EVID, "条目", len(EVIDENCE["entries"]))

    data = json.loads(RULES.read_text(encoding="utf-8"))
    rules = data["rules"]
    ids = {r["id"] for r in rules}
    if CYANO_RULE["id"] in ids:
        print("规则已存在，跳过：", CYANO_RULE["id"])
    else:
        rules.append(CYANO_RULE)
        RULES.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("新增规则", CYANO_RULE["id"], "；规则总数", len(rules))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
