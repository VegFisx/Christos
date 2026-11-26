# -*- coding: utf-8 -*-
"""第四轮：再补 4 条缺口探针（甘遂2、地黄HMF、吴茱萸）。

目标是把「现有 11 条规则覆盖不到的炮制化学」凑成一张可执行的缺口表，
不是提高分数。规则不改。

新增：
  · 甘遂 醋炙：二酯型 ingenol 二萜 → 单酯 → ingenol / 20-deoxyingenol
    （单轮预计 miss，多轮 r3 预计到苷元）；
  · 地黄 九蒸九晒：果糖 → 5-HMF（连续脱水/环化；单轮和多轮都预计 miss）；
  · 吴茱萸 炒制：吴茱萸碱 → 吴茱萸次碱（氧化/芳构化；两模式都预计 miss）。

用法：
    python tools\\add_holdout_cases_round4.py
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
        "id": "gansui_diester_ingenol",
        "herb_cn": "甘遂",
        "herb_en": "Euphorbia kansui",
        "process_cn": "醋炙",
        "process_en": "vinegar-frying",
        "condition": "炮制·醋炙",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN008999",
            "name": "3-O-(2'E,4'Z-decadienoyl)-20-O-acetylingenol",
            "formula": "C32H44O7",
        },
        "targets": [
            {
                "label": "ingenol",
                "kind": "key",
                "value": "HBIN030161",
                "formula": "C20H28O5",
                "family": ["hydrolysis_ester"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "醋炙使二酯型 ingenol 二萜经酯键水解：先脱 20-O-乙酰基生成"
                "3-O-(2'E,4'Z-decadienoyl)ingenol（HBIN009001），再脱 3-O-癸二烯酰基"
                "生成 ingenol。单轮预计只到单酯；多轮 r3 预计到 ingenol。"
            ),
        },
        "literature_note": (
            "DOI 10.19540/j.cnki.cjcmm.20230303.301（刘寒香等，"
            "基于毒性成分转化的甘遂醋炙工艺优选，中国中药杂志 2023, 48(11):2958-2967）"
        ),
    },
    {
        "id": "gansui_kpc_deoxyingenol",
        "herb_cn": "甘遂",
        "herb_en": "Euphorbia kansui",
        "process_cn": "醋炙",
        "process_en": "vinegar-frying",
        "condition": "炮制·醋炙",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN032056",
            "name": "Kansuiphorin C",
            "formula": "C29H34O6",
        },
        "targets": [
            {
                "label": "20-deoxyingenol",
                "kind": "key",
                "value": "HBIN003394",
                "formula": "C20H28O4",
                "family": ["hydrolysis_ester"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "KPC 经酯键水解先到 5-O-benzoyl-20-deoxyingenol（HBIN011834），"
                "再脱苯甲酰基到 20-deoxyingenol。单轮预计只到单酯；多轮 r3 预计到苷元。"
            ),
        },
        "literature_note": (
            "DOI 10.19540/j.cnki.cjcmm.20230303.301（刘寒香等，"
            "基于毒性成分转化的甘遂醋炙工艺优选，中国中药杂志 2023, 48(11):2958-2967）"
        ),
    },
    {
        "id": "dihuang_fructose_hmf",
        "herb_cn": "地黄",
        "herb_en": "Rehmannia glutinosa",
        "process_cn": "九蒸九晒（多次蒸制）",
        "process_en": "repeated steaming and drying",
        "condition": "炮制·蒸制",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN026793",
            "name": "Fructose",
            "formula": "C6H12O6",
        },
        "targets": [
            {
                "label": "5-HMF",
                "kind": "key",
                "value": "HBIN029444",
                "formula": "C6H6O3",
                "family": ["maillard", "condensation", "dehydration"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "5-HMF 由果糖/葡萄糖连续脱水并环化生成（净失 3 分子水）。"
                "maillard_simplified_001 只把 α-羟基醛氧化成二羰基；"
                "elimination_dehydration_001 每次只脱一分子水，且没有呋喃环化规则；"
                "单轮与多轮预计都到不了 5-HMF。"
            ),
        },
        "literature_note": (
            "DOI 10.1155/2022/3382333（Xue et al., Changes in the Chemical Components "
            "of Processed Rehmanniae Radix Distillate during Different Steaming Times; "
            "PMC8872652）；5-HMF 随蒸制增加另见中草药 2016 与 Foods 2025 "
            "DOI 10.3390/foods14223932。"
        ),
    },
    {
        "id": "wuzhuyu_evodiamine_rutaecarpine",
        "herb_cn": "吴茱萸",
        "herb_en": "Evodia rutaecarpa",
        "process_cn": "炒制（加热）",
        "process_en": "stir-frying",
        "condition": "炮制·炒黄",
        "holdout_strength": "strong",
        "seed": {
            "iid": "HBIN026264",
            "name": "Evodiamine",
            "formula": "C19H17N3O",
        },
        "targets": [
            {
                "label": "rutaecarpine",
                "kind": "key",
                "value": "HBIN042657",
                "formula": "C18H13N3O",
                "family": ["demethylation", "oxidation", "aromatization"],
            }
        ],
        "bridge": "",
        "expected": {
            "status": "miss",
            "rule": "",
            "confidence": "high",
            "reason": (
                "加热下吴茱萸碱盐酸盐脱去 CH3Cl 并氧化/芳构化为吴茱萸次碱"
                "（C19H17N3O → C18H13N3O）。demethylation_n_001 只做 N-甲基水解，"
                "净失 CH2，产物是 C18H15N3O 的去甲吴茱萸碱，不是 C18H13N3O 的"
                "吴茱萸次碱；也没有氧化/芳构化规则。"
            ),
        },
        "literature_note": (
            "The Quinazolinocarbolines, Chapter 4（ScienceDirect S1876081308600433）："
            "evodiamine hydrochloride 加热脱 CH3Cl 生成 rutaecarpine；"
            "加热使 rutaecarpine 升高见中国实验方剂学杂志 2011, 17(7)"
            "（析因设计法研究炮制对吴茱萸中3种主要成分的影响）。"
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
    d["strong_expansion_note_round4"] = (
        "2026-11-22 第四轮新增 4 条 strong 缺口探针（甘遂2、地黄5-HMF、吴茱萸）。"
        "甘遂单轮预期 miss、多轮 r3 预期 consistent；地黄5-HMF 与吴茱萸两模式均 miss。"
        "规则未改；expected 在运行前写入并提交。"
    )

    HOLDOUT.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("写入 %s；新增 %d 例；strong=%d weak=%d total=%d"
          % (HOLDOUT, added, strong, weak, len(cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
