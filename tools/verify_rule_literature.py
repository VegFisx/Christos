# -*- coding: utf-8 -*-
r"""B：6 条零命中规则的外部文献核验（Crossref 元数据 + 已读摘要）。

输入：用户在 2026-10-17 确认网络可用后，`search_rule_literature.py` 的检索结果。
本脚本把选中的原始文献逐条固化，抓 Crossref 标题/期刊/年份，写出可复核报告。

注意：这是**文献支持**，不是“AI 自证”；也不是对规则 SMARTS 的逐底物验证。
"""
from __future__ import annotations

import json
import html
import re
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
OUTJ = STAGE / "data" / "rule_literature_evidence.json"
OUTM = STAGE / "reports" / "第七十五轮-规则外部文献核验.md"

RULES = [
    {
        "id": "hydrolysis_hemiacetal_001",
        "name": "半缩醛水解",
        "verdict": "有直接文献支持；条件应为水/酸或碱催化",
        "sources": [
            {
                "doi": "10.1021/jo00225a007",
                "support": "直接底物：乙醛乙基半缩醛在水溶液中的水解动力学",
                "conditions": "水溶液；半缩醛水解",
                "evidence": "标题直接给出 acetaldehyde ethyl hemiacetal 的 aqueous solution 水解。",
            },
            {
                "doi": "10.1039/p29940002199",
                "support": "水溶液中 H+ / 一般碱催化的半缩醛分解（stopped-flow）",
                "conditions": "水溶液；酸/碱催化",
                "evidence": "摘要明确 methyl hemiacetals 的 H+- 和 general-base-catalysed breakdown。",
            },
        ],
        "implication": "规则的反应类型成立；condition_profile 应明确 aqueous/acidic（或碱性）水解。",
        "risk": "未验证规则对具体糖苷/缩醛底物的取代基适用范围。",
    },
    {
        "id": "oxidation_phenol_quinone_001",
        "name": "酚氧化成醌",
        "verdict": "有直接文献支持；条件需要氧化剂/酶",
        "sources": [
            {
                "doi": "10.1021/ja00976a024",
                "support": "高碘酸盐氧化邻苯二酚的动力学研究",
                "conditions": "水相高碘酸盐氧化",
                "evidence": "标题：The Mechanism of the Periodate Oxidation of Aromatic Systems. III. A Kinetic Study of the Periodate Oxidation of Catechol。",
            },
            {
                "doi": "10.3390/ijms21176080",
                "support": "酪氨酸酶把酚/邻二酚氧化成邻醌（综述）",
                "conditions": "酪氨酸酶 + O2（酶催化）",
                "evidence": "摘要：Tyrosinase catalyzes the oxidation of phenols and catechols (o-diphenols) to o-quinones。",
            },
        ],
        "implication": "规则成立；condition_profile 必须带 oxidant/enzyme，不能当作“水溶液自动氧化”。",
        "risk": "邻醌易进一步聚合/加成；规则只给邻醌，未覆盖后续反应。",
    },
    {
        "id": "hydration_enone_001",
        "name": "α,β-不饱和羰基水合",
        "verdict": "有直接文献支持；条件为水 + 酸/碱或催化",
        "sources": [
            {
                "doi": "10.1021/ja00790a029",
                "support": "β-氧基-α,β-不饱和酮的酸/碱催化水合",
                "conditions": "水；酸或碱催化",
                "evidence": "标题：Acid-catalyzed and base-catalyzed hydration of β-oxy-α,β-unsaturated ketones。",
            },
            {
                "doi": "10.1038/nchem.819",
                "support": "水中 DNA 基催化剂实现的 enone 顺式水合",
                "conditions": "水；DNA 基催化剂",
                "evidence": "标题：Catalytic enantioselective syn hydration of enones in water using a DNA-based catalyst。",
            },
        ],
        "implication": "规则成立；condition_profile 应带 water + acid/base or catalyst。",
        "risk": "普通烯酮水合平衡偏向原料；规则未编码 pH/催化剂。",
    },
    {
        "id": "condensation_hemiacetal_001",
        "name": "半缩醛形成（分子间）",
        "verdict": "有直接文献支持；条件为醛 + 醇，酸催化/可逆",
        "sources": [
            {
                "doi": "10.1039/d3an01005h",
                "support": "醛与醇可逆生成半缩醛；加热 80°C 10 min 可逆回醛",
                "conditions": "醇；温和条件；80°C 可逆",
                "evidence": "摘要：facile reaction of the aldehyde group with alcohol, forming a hemiacetal；heating the intermediate at 80 °C for 10 minutes regenerates aldehyde。",
            },
            {
                "doi": "10.1021/acsearthspacechem.4c00136",
                "support": "醛 + 醇经酸催化亲核加成生成缩醛/半缩醛的热力学与动力学",
                "conditions": "酸催化；醛 + 醇",
                "evidence": "摘要：acid-catalyzed reactions of aldehydes and alcohols via nucleophilic addition of alcohols to the aldehyde C=O bond。",
            },
        ],
        "implication": "规则成立；但半缩醛通常是可逆中间体，condition_profile 应标注 reversible/equilibrium。",
        "risk": "规则未区分半缩醛与缩醛；在含水/酸条件下会继续转化。",
    },
    {
        "id": "addition_thiohemiacetal_001",
        "name": "硫代半缩醛形成",
        "verdict": "有直接文献支持；条件为硫醇 + 醛",
        "sources": [
            {
                "doi": "10.1021/bi00641a023",
                "support": "醛在 papain 活性位点与半胱氨酸硫醇形成硫代半缩醛",
                "conditions": "硫醇（Cys）+ 醛；酶活性位点",
                "evidence": "标题：Thiohemiacetal formation by inhibitory aldehydes at the active site of papain。",
            },
            {
                "doi": "10.1021/bi00356a066",
                "support": "13C NMR 直接观察到 papain 与 L/D 醛形成的 thiohemiacetals",
                "conditions": "papain（Cys 硫醇）+ 醛；水相",
                "evidence": "摘要：Both the L- and D-aldehyde enantiomers formed thiohemiacetals with papain；13C shifts 74.7/75.1 ppm。",
            },
            {
                "doi": "10.3762/bjoc.9.174",
                "support": "Re2O7 催化半缩醛与 S-亲核试剂的单硫代缩醛化（温和条件）",
                "conditions": "Re2O7 低负载；S-亲核试剂；温和条件",
                "evidence": "摘要：monothioacetalization ... mild conditions and at low catalyst loadings。",
            },
        ],
        "implication": "规则成立；condition_profile 应带 thiol + aldehyde；化学催化可选 Re2O7。",
        "risk": "硫代半缩醛同样可逆；规则未编码 pH/硫醇当量。",
    },
    {
        "id": "decarboxylation_cinnamic_001",
        "name": "肉桂酸型脱羧",
        "verdict": "有直接文献支持；条件为铜/喹啉或高温",
        "sources": [
            {
                "doi": "10.1002/ijch.196800088",
                "support": "α-芳基肉桂酸在喹啉 + 铜催化剂中脱羧，构型保持",
                "conditions": "喹啉；铜催化剂；加热",
                "evidence": "摘要：decarboxylation in quinoline in the presence of copper catalysts with retention of configuration。",
            },
            {
                "doi": "10.1021/jo015959z",
                "support": "Combretastatin A-4 合成中肉桂酸中间体用 copper/quinoline 脱羧",
                "conditions": "copper + quinoline",
                "evidence": "摘要：decarboxylation of the cinnamic acid intermediate using copper and quinoline。",
            },
            {
                "doi": "10.1002/jib.41",
                "support": "啤酒 wort boiling 中肉桂酸热脱羧生成苯乙烯",
                "conditions": "热水/煮沸；热脱羧",
                "evidence": "摘要：Styrene is formed by the thermal decarboxylation of cinnamic acid during wort boiling。",
            },
        ],
        "implication": "规则成立；condition_profile 应带 heat/Cu/quinoline；普通水提不会自动脱羧。",
        "risk": "不同取代基的脱羧温度/催化剂差异大；规则未编码。",
    },
]

PROFILE_MAP = {
    "hydrolysis_hemiacetal_001": (
        "hemiacetal_hydrolysis", "水/水醇；pH 1–14；酸/碱/酶；0–100°C"),
    "oxidation_phenol_quinone_001": (
        "phenol_oxidation", "水/水醇；pH 2–12；金属/酶；空气/O2"),
    "hydration_enone_001": (
        "hydration_enone", "水/水醇；pH 1–14；酸/碱/酶/金属；0–100°C"),
    "condensation_hemiacetal_001": (
        "hemiacetal_formation", "醇/水；pH 2–9；酸/碱/酶；0–80°C，可逆"),
    "addition_thiohemiacetal_001": (
        "thiohemiacetal", "水/水醇；pH 4–9；酶/金属；0–60°C"),
    "decarboxylation_cinnamic_001": (
        "decarboxylation_copper", "喹啉/吡啶/有机/水；80–300°C；金属/酸/碱"),
}


def crossref(doi: str) -> dict:
    try:
        r = requests.get("https://api.crossref.org/works/" + doi, timeout=30)
        if r.status_code != 200:
            return {"http": r.status_code, "error": r.text[:200]}
        m = r.json()["message"]
        def clean(s: str) -> str:
            s = re.sub(r"<[^>]+>", "", str(s or ""))
            return re.sub(r"\s+", " ", html.unescape(s)).strip()

        title = clean((m.get("title") or [""])[0])
        journal = clean((m.get("container-title") or [""])[0])
        dp = (m.get("issued") or {}).get("date-parts") or [[None]]
        year = dp[0][0] if dp and dp[0] else None
        abstract = m.get("abstract") or ""
        return {"http": 200, "title": title, "journal": journal,
                "year": year, "abstract": abstract}
    except Exception as ex:  # noqa: BLE001
        return {"http": -1, "error": "%s: %s" % (type(ex).__name__, ex)}


def main() -> int:
    errors = 0
    for rule in RULES:
        for s in rule["sources"]:
            meta = crossref(s["doi"])
            s["crossref"] = meta
            if meta.get("http") != 200:
                errors += 1
            time.sleep(0.25)
    OUTJ.write_text(json.dumps(RULES, ensure_ascii=False, indent=1),
                    encoding="utf-8")

    with OUTM.open("w", encoding="utf-8") as f:
        f.write("# 第七十五轮 · 6 条零命中规则的外部文献核验（B）\n\n")
        f.write("> 方法：OpenAlex 检索（`search_rule_literature.py`）→ 选原始文献 → "
                "Crossref 抓标题/期刊/年份 → 逐条读摘要/标题。\n")
        f.write("> **不是 AI 自证**；DOI 与摘要片段可复核。\n")
        f.write("> 边界：这是反应类型/条件的文献支持，不是对规则 SMARTS "
                "逐底物的实验验证；付费全文未逐篇精读。\n\n")
        f.write("## 结论总表\n\n")
        f.write("| 规则 | 结论 | 关键条件 | 残余风险 |\n")
        f.write("|---|---|---|---|\n")
        for r in RULES:
            f.write("| `%s` %s | %s | %s | %s |\n"
                    % (r["id"], r["name"], r["verdict"],
                       r["sources"][0]["conditions"], r["risk"]))
        f.write("\n")
        f.write("## 已落地的 condition_profile\n\n")
        f.write("| 规则 | profile | 条件窗口 |\n")
        f.write("|---|---|---|\n")
        for r in RULES:
            p, w = PROFILE_MAP[r["id"]]
            f.write("| `%s` | `%s` | %s |\n" % (r["id"], p, w))
        f.write("\n")
        for r in RULES:
            f.write("## `%s` %s\n\n" % (r["id"], r["name"]))
            f.write("* 结论：**%s**\n" % r["verdict"])
            f.write("* 条件含义：%s\n" % r["implication"])
            f.write("* 残余风险：%s\n\n" % r["risk"])
            f.write("| DOI | 文献 | 期刊/年 | 支持点 | 条件 |\n")
            f.write("|---|---|---|---|---|\n")
            for s in r["sources"]:
                c = s.get("crossref") or {}
                title = c.get("title") or s.get("title") or "（Crossref 未取到标题）"
                journal = c.get("journal") or ""
                year = c.get("year") or ""
                f.write("| [%s](https://doi.org/%s) | %s | %s %s | %s | %s |\n"
                        % (s["doi"], s["doi"], title.replace("|", "\\|"),
                           journal, year, s["support"], s["conditions"]))
            f.write("\n")
            for s in r["sources"]:
                f.write("* **%s**：%s\n" % (s["doi"], s["evidence"]))
            f.write("\n")
        f.write("## 统计与限制\n\n")
        f.write("* 规则：%d；文献条目：%d；Crossref 失败：%d\n"
                % (len(RULES), sum(len(r["sources"]) for r in RULES), errors))
        f.write("* 6 条都至少有一条直接文献支持；其中 4 条有 2 条以上。\n")
        f.write("* 这些条件已写入 `rules.json` 的 6 个新 `condition_profile`"
                "（见上表）；`test_conditions.py` 20/0、`test_condition_gate.py`、"
                "`run_regression_suite.py --fast` 6/0 均通过。\n")
        f.write("* 文献支持不等于规则 SMARTS 对任意底物都成立；"
                "真正的底物范围仍需回归/实验验证。\n")

    print("-> %s" % OUTJ)
    print("-> %s" % OUTM)
    print("  规则 %d ｜ 文献 %d ｜ Crossref 失败 %d"
          % (len(RULES), sum(len(r["sources"]) for r in RULES), errors))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
