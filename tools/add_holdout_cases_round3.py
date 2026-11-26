# -*- coding: utf-8 -*-
"""第三轮：加入两个「缺口探针」strong 案例（柴胡、黄柏）。

目的不是提高分数，而是把现有规则覆盖不到的两类炮制化学写进留出集：

  · 柴胡 醋炙：柴胡皂苷 A（13,28-五元环醚）→ 柴胡皂苷 b1（开环异构体）；
  · 黄柏 盐炙：巴马汀（芳香 O-甲基）→ 巴马红汀（O-去甲基）。

两条都按现有规则判为 miss，expected 在运行前写入并提交。规则不改。

用法：
    python tools\\add_holdout_cases_round3.py
"""

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT = ROOT / "data" / "holdout_paozhi.json"

NEW_CASES = [
    {
        "id": "chaihu_saikosaponin_a_b1",
        "herb_cn": "柴胡",
        "herb_en": "Bupleurum chinense",
        "process_cn": "醋炙",
        "process_en": "vinegar-frying",
        "condition": "炮制·醋炙",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN042787",
            "name": "Saikosaponin a",
            "formula": "C42H68O13",
        },
        "targets": [
            {
                "label": "saikosaponin b1",
                "kind": "key",
                "value": "HBIN042789",
                "formula": "C42H68O13",
                "family": ["isomerization", "rearrangement"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "醋炙/酸性条件下柴胡皂苷 A 的 13,28-环氧醚键开环，异构化为柴胡皂苷 b1"
                "（同分子式 C42H68O13，环数 8→7）。现有规则只有三元环氧化物开环"
                "（hydrolysis_epoxide_001，SMARTS 为 [C]1[O][C]1）和非环醚水解"
                "（cleavage_ether_acyclic_001，[CX4;!R][O][CX4;!R]），都不匹配"
                "13,28-五元环醚；也没有异构化规则。"
            ),
        },
        "literature_note": (
            "DOI 10.7501/j.issn.0253-2670.2017.02.019（于蓓蓓等，"
            "基于HPLC-DAD-MSn的柴胡皂苷A的体外生物转化研究，"
            "中草药 2017, 48(2):333-338）；醋制 I 型→II 型见"
            "中国药科大学学报 2012, 43(4):334-342。"
        ),
    },
    {
        "id": "huangbo_palmatine_palmatrubine",
        "herb_cn": "黄柏",
        "herb_en": "Phellodendron chinense",
        "process_cn": "盐炙（150–160 °C）",
        "process_en": "salt-frying",
        "condition": "炮制·盐炙",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN038666",
            "name": "Palmatine",
            "formula": "C21H22NO4+",
        },
        "targets": [
            {
                "label": "palmatrubine",
                "kind": "key",
                "value": "HBIN038670",
                "formula": "C20H20NO4+",
                "family": ["demethylation"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "盐炙 150–160 °C 使巴马汀的芳香甲氧基脱甲基生成巴马红汀"
                "（C21H22NO4+ → C20H20NO4+）。现有 demethylation_n_001 只匹配"
                "N-甲基（[N;!a][CH3]）；cleavage_ether_acyclic_001 只匹配"
                "非环烷基醚（[CX4;!R][O][CX4;!R]），均不覆盖芳香 O-甲基。"
            ),
        },
        "literature_note": (
            "DOI 10.3969/j.issn.1001-1528.2010.03.028（祁东利等，"
            "黄柏炮制后化学成分转化研究，中成药 2010, 32(3):443-447）；"
            "巴马汀→巴马红汀见中成药 2021, 43(11):3082-3088 与"
            "现代药物与临床 2015, 30(1):18-23。"
        ),
    },
]


def main() -> int:
    d = json.loads(HOLDOUT.read_text(encoding="utf-8"))
    cases = d.setdefault("cases", [])
    have = {c.get("id") for c in cases}
    added = 0
    for c in NEW_CASES:
        if c["id"] in have:
            print("已存在，跳过：%s" % c["id"])
            continue
        cases.append(c)
        have.add(c["id"])
        added += 1

    strong = sum(1 for c in cases if c.get("holdout_strength") == "strong")
    weak = sum(1 for c in cases if c.get("holdout_strength") == "weak")
    d["tiers"] = {
        "strong": "只把这 %d 例的分数当作独立留出" % strong,
        "weak": "规则设计/证据文献已覆盖的案例，只作回归集，不当作独立验证（共 %d 例）" % weak,
    }
    d["strong_expanded_at"] = "2026-11-22"
    d["strong_expansion_note_round3"] = (
        "2026-11-22 第三轮新增 2 条 strong 缺口探针（柴胡、黄柏），"
        "预期均为 miss：柴胡 13,28-五元环醚开环/异构化、黄柏芳香 O-去甲基，"
        "现有 11 条证据规则都不覆盖。规则未改；expected 在运行前写入并提交。"
    )

    HOLDOUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("写入 %s；新增 %d 例；strong=%d weak=%d total=%d"
          % (HOLDOUT, added, strong, weak, len(cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
