#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 conditions/template_provenance.json —— 21 个预置条件档的出处登记。

为什么要有这个文件（第 101 轮 A8）：
    用户 2026-11-04：「禁止AI自己猜测…起码得有参考文献」。
    `conditions/templates.py` 里的温度/时长原来看起来像实测值，其实分三类：
      · 有同行评议文献支撑（炮制若干档，数字直接来自论文）；
      · 只有二手网页/教材区间（炒黄/炒焦/炒炭）；
      · 工艺惯例（煎煮 100 °C/60 min、醇提取乙醇沸点…）。
    这里把三类分开登记，**引文全部从 reports/paper/paozhi_sources_20261031.json
    原样搬运**，不手写 DOI 与引句（AGENTS §三：不要手写数据）。

用法：
    python -I tools\\gen_template_provenance.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "conditions",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SRC = ROOT / "reports" / "paper" / "paozhi_sources_20261031.json"
OUT = ROOT / "conditions" / "template_provenance.json"

# 模板名 -> (状态, 引文索引列表, 匹配程度, 说明)
#   状态：cited=同行评议；secondary=二手来源；convention=工艺惯例；physics=物理常数
MAP = {
    "自定义": ("convention", [], "", "用户自填条件的占位档，本身没有物理含义。"),
    "煎煮": ("convention", [], "", "中药汤剂标准工艺：常压水煮约 1 h。属工艺惯例，非实测最优值。"),
    "水提": ("convention", [], "", "60 °C / 120 min 为温和水提惯例，无原始文献。"),
    "醇提": ("physics", [], "", "78 °C 取乙醇常压沸点（物理常数）；120 min 为工艺惯例。"),
    "酸水解": ("convention", [], "", "刻意强酸长时加热以断糖苷/酯键；pH 1.5 / 120 min 为惯例值。"),
    "碱水解": ("convention", [], "", "刻意强碱长时加热；pH 12 / 120 min 为惯例值。"),
    "氧化": ("convention", [], "", "通氧 + 长时间；240 min 为惯例值，无出处。"),
    "还原": ("convention", [], "", "H2 氛围 + 金属催化，作为对照档；数值为惯例。"),
    "酶催化": ("convention", [], "", "37 °C / pH 6 / 24 h 模拟体内或发酵，属惯例。"),
    "室温浸泡": ("convention", [], "", "极端对照：25 °C / 24 h。"),
    "无氧煎煮": ("convention", [], "", "煎煮的 N2 气氛对照，其余同煎煮。"),
    "无溶剂（炮制）": ("convention", [], "", "150 °C / 30 min；炒制常见区间 120–180 °C 的中间值。"),
    "炮制·炒黄": ("cited", [2, 1, 3], "representative",
                "模板 165 °C / 10 min 落在文献区间内（160–170 °C；莱菔子 160 °C/3 min；120 °C/0–10 min）。"),
    "炮制·炒焦": ("secondary", [4], "representative",
                  "模板 195 °C / 10 min 取『焦炒 190–200 °C』区间中值；来源为二手网页。"),
    "炮制·炒炭": ("secondary", [5], "representative",
                  "模板 260 °C / 35 min 取『220–300 °C、35–40 min』区间；来源为二手网页。"),
    "炮制·蜜炙": ("cited", [0], "exact",
                  "120 °C / 13.5 min 与文献数值完全一致（甘草蜜炙，700 W）。"),
    "炮制·酒炙": ("cited", [10], "rounded",
                  "模板 140 °C / 5 min 取『柴胡黄酒 135–145 °C、5 min』中值。"),
    "炮制·醋炙": ("cited", [11], "exact",
                  "84 °C / 35 min 与文献完全一致（延胡索米醋 37%）。"),
    "炮制·盐炙": ("cited", [12, 13], "exact",
                  "150 °C / 10 min 取杜仲盐炙；另有沙苑子 2% 盐水 100 °C/15 min。"),
    "炮制·姜炙": ("cited", [14], "exact",
                  "150 °C / 40 min 与文献一致（黄连 15% 姜汁）。"),
    "炮制·蒸制": ("cited", [9], "representative",
                  "模板 100 °C / 120 min 取『人参 95–100 °C、2–3 h』区间端点；蒸汽未单独建模。"),
}


def main() -> int:
    import templates as T                      # noqa: E402

    src = json.loads(SRC.read_text(encoding="utf-8"))
    conds = src.get("conditions") or []

    missing = sorted(set(T.TEMPLATES) - set(MAP))
    extra = sorted(set(MAP) - set(T.TEMPLATES))
    if missing or extra:
        print("映射与模板不一致：缺 %s / 多 %s" % (missing, extra))
        return 1

    out = {"schema": "chemreact-template-provenance/1",
           "generated": "2026-11-04",
           "why": "用户 2026-11-04：涉及底层反应逻辑的参数必须有参考文献；没有出处的只能当惯例。",
           "source_file": str(SRC.relative_to(ROOT)).replace("\\", "/"),
           "status_vocabulary": {
               "cited": "有同行评议文献，数值可追溯",
               "secondary": "只有二手来源（百科/教学站），可参考不可当实验值",
               "convention": "工艺惯例或对照档，文献里没有『最优值』这一说",
               "physics": "物理常数（如沸点）"},
           "templates": {}}

    for name, tpl in T.TEMPLATES.items():
        status, idxs, match, note = MAP[name]
        cites = []
        for i in idxs:
            c = conds[i]
            sr = c.get("source") or {}
            cites.append({
                "method": c.get("method"),
                "herb": c.get("herb"),
                "value": c.get("value"),
                "unit": c.get("unit"),
                "time": c.get("time"),
                "quote": c.get("quote"),
                "source": {k: sr.get(k) for k in ("title", "journal", "publisher", "year", "doi", "url", "type") if sr.get(k)},
            })
        out["templates"][name] = {
            "status": status,
            "match": match,
            "template_values": {"temperature": tpl.temperature, "time_min": tpl.time_min,
                                "solvent": tpl.solvent, "pH": tpl.pH,
                                "catalyst": tpl.catalyst, "atmosphere": tpl.atmosphere},
            "note": note,
            "citations": cites,
        }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = {}
    for v in out["templates"].values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print("写出 %s" % OUT)
    print("模板 %d 个；状态分布 %s" % (len(out["templates"]), counts))
    for name, v in out["templates"].items():
        doi = ""
        for c in v["citations"]:
            if (c.get("source") or {}).get("doi"):
                doi = " " + c["source"]["doi"]
                break
        print("  %-14s %-10s %s%s" % (name, v["status"], v["match"] or "-", doi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
