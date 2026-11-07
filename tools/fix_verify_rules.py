# -*- coding: utf-8 -*-
r"""修最后 2 条 verify 规则的 SMARTS。

【分子内半缩醛化】——链条写错了
    错: [CX3H1:1]=[OX1:2][CX4:3]...     读作 C1=O2，且 O2 再连 C3
    对: [CX3H1:1](=[OX1:2])[CX4:3]...   读作 C1(=O2)，O2 是【分支】
    实证：4-羟基丁醛 O=CCCCO → 2-羟基四氢呋喃

【分子内酰胺化】——两个问题
    a) 反应物里没写羧基的 OH，导致配平账目不清
    b) 产物把氮写成 [NX3H2]，但成环后氮是 2 个重原子邻居 + 2 H = 4 价，非法
       应写成 [NX3H1]（内酰胺的 NH）
    实证：4-氨基丁酸 → γ-丁内酰胺 + 水

【肉桂酸型脱羧】——本来就是对的，不该标 verify
    手工底物（肉桂酸/咖啡酸/阿魏酸）全部正确产出苯乙烯型产物 + CO2。
    校验器报「无底物匹配」只是因为 2500 个样本里恰好没有这类分子——
    「样本里没有」≠「规则是错的」。
"""
import json
from pathlib import Path

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
F = STAGE / "rules" / "rules.json"
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

FIXES = {
    "cyclization_hemiacetal_001": {
        "smarts": ("[CX3H1:1](=[OX1:2])[CX4:3][CX4:4][CX4:5][OX2H:6]"
                   ">>[C:1]1([OH:2])[CX4:3][CX4:4][CX4:5][O:6]1"),
        "status": "draft",
        "notes": ("★已修★ SMARTS 链写错了：原来写成 C1=O2-C3-...，"
                  "意思是碳氧双键后氧【再连】C3；正确应是 O2 作为 C1 的【分支】，"
                  "即 [CX3H1:1](=[OX1:2])[CX4:3]...。"
                  "实证：4-羟基丁醛 O=CCCCO → 2-羟基四氢呋喃。"),
    },
    "cyclization_lactam_001": {
        "smarts": ("[CX3:1](=[OX1:2])([OX2H:7])[CX4:3][CX4:4][CX4:5][NX3H2:6]"
                   ">>[C:1]1(=[O:2])[CX4:3][CX4:4][CX4:5][NX3H1:6]1.[OH2:7]"),
        "status": "draft",
        "notes": ("★已修★ 两处问题："
                  "① 反应物里漏了羧基的 OH，配平账目不清；"
                  "② 产物把氮写成 [NX3H2]，但成环后氮有 2 个重原子邻居 + 2 个 H "
                  "= 4 价，中性氮只能 3 价，所以 RDKit 报「价态非法」；"
                  "内酰胺的氮应该是 [NX3H1]。"
                  "实证：4-氨基丁酸 → γ-丁内酰胺 + 水。"),
    },
}

for rid, patch in FIXES.items():
    if rid in by_id:
        by_id[rid].update(patch)
        print(f"[修] {by_id[rid]['name']}")
        print(f"     {patch['smarts']}")

# 肉桂酸型脱羧：手工底物已验证可用，转正
if "decarboxylation_cinnamic_001" in by_id:
    r = by_id["decarboxylation_cinnamic_001"]
    r["status"] = "active"
    r["notes"] = (r.get("notes", "") +
                  " 【已用人工底物验证：肉桂酸→苯乙烯+CO2、咖啡酸、阿魏酸 全部正确。"
                  "校验器报「无底物匹配」只是因为样本里恰好没有这类分子——"
                  "「样本里没有」≠「规则是错的」。】")
    print(f"[转正] {r['name']}（人工底物已验证）")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n规则总数 {len(data['rules'])}")
