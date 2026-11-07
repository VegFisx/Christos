# -*- coding: utf-8 -*-
"""清理 rules.json：修好被 !@ 删除弄残的注释，并更新已验证规则的状态。"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))

NOTES = {
    "hydrolysis_ester_001":
        "实测差值 O1H2，补 1 分子水即配平。乌头碱减毒主途径。"
        "引擎须用 RDChiral：rdkit 原生 RunReactants 在环内断键时会复制原子。",
    "hydrolysis_glycoside_001":
        "实测差值 O1H2，补 1 分子水。皂苷脱糖生成苷元。"
        "糖环本身是环，RDChiral 能正确打开糖苷键并保持糖环完整。",
    "hydrolysis_amide_001":
        "实测差值 O1H2。★已修两类映射缺陷："
        "①原写法反应物 [N:3] 与产物 [O:3] 共用编号 3，rdkit 会把氮原子当氧改；"
        "②新增原子必须【不编号】（写 [OH] 而非 [O:5]），否则 RDChiral 抛 KeyError。"
        "中性水中酰胺水解实际很慢，条件层应压制其分数。",
    "hydrolysis_sulfate_001":
        "实测差值 O1H2。常见于硫酸多糖。底物稀少（4000 个真实分子里只 4 个匹配），"
        "统计置信度低。",
    "hydrolysis_phosphate_001":
        "实测差值 O1H2。磷脂、磷酸糖。环磷酸酯由 RDChiral 通用处理，无需单独规则。",
    "hydrolysis_acetal_001":
        "★原 SMARTS 有真错误：产物只写了 [#6:5]，把 [#6:3] 整个片段丢了（丢一个烷氧基）。"
        "已补第三个产物片段 [OH][#6:3]。修复后 400/400 配平。",
    "hydrolysis_hemiacetal_001":
        "简单底物（COC(O)c1ccccc1）配平正确且不耗水。"
        "环状半缩醛（如葡萄糖）由 RDChiral 正确开环。",
    "oxidation_amine_001":
        "实测差值 O1。氧化脱氨。★已修两类映射缺陷："
        "①原写法反应物 [N:2] 与产物 [O:2] 共用编号 2，rdkit 会把氮原子当氧改"
        "（数值凑巧还能配平，极具迷惑性）；②新增原子必须【不编号】（写 [O] 而非 [O:5]）。"
        "底物稀少（只 5 个匹配），权重应压低。",
    "decarboxylation_beta_keto_001":
        "★原 SMARTS 有真错误：产物漏写 CO2（实测差值 C-1 O-2）。已补 [C](=[O])=[O]。"
        "对照：同文件的「芳香酸脱羧」写法正确，CO2 显式写入产物——两种写法并存说明是笔误。",
    "esterification_intramolecular_001":
        "★★坏规则★ 19 个真实底物能匹配，产出 0 个产物。环闭合产物写法有误。"
        "已停用（status=disabled），待重写。分子内酯化是真实反应（羟基酸→内酯），值得修好。",
    "tautomerization_keto_enol_001":
        "实测 509/509 配平。属互变异构，不产生新分子，级联中应默认跳过。",
    "hydroxylation_aromatic_001":
        "实测 1895/1895 配平，但传播过广（400 个底物出 1895 个产物），且方向不明确。"
        "建议加位置/取代约束后降权重用。",
    "hydration_alkene_001":
        "实测配平，但 SMARTS 无区域选择性，任意双键都加水，产物质量差。建议重写（马氏规则）。",
    "hydration_enone_001":
        "实测配平，但无立体/区域选择性。建议重写。",
    "demethylation_aromatic_001":
        "实测差值 O1H2。⚠️ SMARTS [O:1][CH3:2] 过宽，会命中脂肪族甲氧基，应加芳香性约束。",
}

STATUS = {
    "hydrolysis_acetal_001": "active",        # 原先 fixed_pending_verify，现已 400/400 验证
    "hydrolysis_hemiacetal_001": "active",    # 原先 verify，现已 44/44 验证
    "decarboxylation_beta_keto_001": "active",  # 原先 fixed_pending_verify
}

changed = []
for r in data["rules"]:
    rid = r["id"]
    if rid in NOTES:
        r["notes"] = NOTES[rid]
        changed.append(f"notes  {rid}")
    if rid in STATUS:
        r["status"] = STATUS[rid]
        changed.append(f"status {rid} -> {STATUS[rid]}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"已更新 {len(changed)} 处：")
for c in changed:
    print("   " + c)
print(f"\n文件已写回：{F}")
