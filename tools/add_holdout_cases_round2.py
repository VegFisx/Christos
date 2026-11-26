# -*- coding: utf-8 -*-
"""第二轮 strong 扩充：槐米（芦丁→槲皮素）、地黄（acteoside→verbasoside）。

预注册纪律：
  · 预期在运行前写入并提交；
  · 不新增/修改任何规则；
  · 只收「文献明确给出结构转化 + 炮制条件 + 底物/产物在 tcm.db 有结构」的案例。

本轮联网检索了陈皮、槐米、山楂、地黄：
  · 槐米、地黄符合条件，各收 1 例；
  · 陈皮：橙皮苷/柚皮苷→苷元这对化学已由枳壳两例覆盖，且炒制文献未见
    橙皮素升高的直接定量，故不收；
  · 山楂：金丝桃苷/异槲皮苷下降、槲皮素可能升高，但缺少条件特异的结构转化
    定量，故不收。

用法：
    python tools\\add_holdout_cases_round2.py
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
        "id": "huaimi_rutin_quercetin",
        "herb_cn": "槐米",
        "herb_en": "Sophora japonica flower bud",
        "process_cn": "炒炭（中度）",
        "process_en": "moderate char-frying",
        "condition": "炮制·炒炭",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN042670",
            "name": "Rutin",
            "formula": "C27H30O16",
        },
        "targets": [
            {
                "label": "quercetin",
                "kind": "key",
                "value": "HBIN041495",
                "formula": "C15H10O7",
                "family": ["hydrolysis_glycoside"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "consistent",
            "rule": "hydrolysis_glycoside_001",
            "confidence": "high",
            "reason": (
                "炒炭过程中芦丁（槲皮素-3-O-芸香糖苷）逐步减少，槲皮素先增后降；"
                "中度炒炭时槲皮素升高，符合芦丁脱糖苷生成槲皮素。"
                "同批 HPLC 定量 6 个成分，芦丁与槲皮素呈反向趋势。"
            ),
        },
        "literature_note": (
            "DOI 10.7501/j.issn.0253-2670.2025.18.010（付毛毛等，"
            "槐米炒炭过程中颜色、成分含量的变化规律和相关性分析，"
            "中草药 2025, 56(18):6602-6611）"
        ),
    },
    {
        "id": "dihuang_acteoside_verbasoside",
        "herb_cn": "地黄",
        "herb_en": "Rehmannia glutinosa",
        "process_cn": "九蒸九晒（多次蒸制）",
        "process_en": "repeated steaming and drying",
        "condition": "炮制·蒸制",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN014630",
            "name": "Acteoside",
            "formula": "C29H36O15",
        },
        "targets": [
            {
                "label": "verbasoside",
                "kind": "key",
                "value": "HBIN047822",
                "formula": "C20H30O12",
                "family": ["hydrolysis_ester"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "consistent",
            "rule": "hydrolysis_ester_001",
            "confidence": "high",
            "reason": (
                "反复蒸制中 acteoside（verbascoside）的咖啡酰酯键水解，"
                "生成 verbasoside（失去咖啡酰基）；文献在炮制地黄馏出物中"
                "检出 verbasoside，并把它归因于 acteoside 降解。"
            ),
        },
        "literature_note": (
            "DOI 10.1155/2022/3382333（Xue et al., Changes in the Chemical "
            "Components of Processed Rehmanniae Radix Distillate during "
            "Different Steaming Times, Evid Based Complement Alternat Med "
            "2022; PMC8872652）"
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
    d["strong_expansion_note_round2"] = (
        "2026-11-22 第二轮联网检索新增 2 条 strong（槐米、地黄）；"
        "陈皮/山楂因缺少条件特异的结构转化证据未纳入。"
        "规则未改；两条 expected 在运行前写入并提交。"
    )
    d["holdout_strength"] = (
        "strong=该化学未被用于设计任何规则；weak=所用规则族的证据文献里出现过同一味药"
        "（但未指名这一对底物/产物）。"
    )

    HOLDOUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("写入 %s；新增 %d 例；strong=%d weak=%d total=%d"
          % (HOLDOUT, added, strong, weak, len(cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
