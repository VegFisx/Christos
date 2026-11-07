# -*- coding: utf-8 -*-
"""按诊断结果给草稿规则定稿：转正 / 标记复核 / 停用。"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")

# 校验器 + 手工探针的结论
ACTIVE = [
    # 校验通过 + 手工探针也通过
    "oxidation_primary_alcohol_001", "oxidation_sulfide_001", "oxidation_epoxide_001",
    "oxidation_dehydrogenation_enone_001",
    "reduction_aldehyde_001", "reduction_alkene_001",
    "hydrolysis_epoxide_001", "hydrolysis_lactam_001", "hydrolysis_imine_001",
    "cyclization_lactone_delta_001", "isomerization_double_bond_001",
    "rearrangement_retro_aldol_001",
    "decarboxylation_malonic_001",   # 样本里没底物，但手工探针（丙二酸/乙酰乙酸）配平
    "elimination_deamination_001",
    # 原有 24 条也一起明确成 active（幂等）
    "hydrolysis_ester_001", "hydrolysis_glycoside_001", "hydrolysis_amide_001",
    "hydrolysis_sulfate_001", "hydrolysis_phosphate_001", "hydrolysis_acetal_001",
    "hydrolysis_hemiacetal_001", "oxidation_hydroxyl_001", "oxidation_aldehyde_001",
    "oxidation_phenol_quinone_001", "oxidation_amine_001", "reduction_ketone_001",
    "reduction_quinone_001", "elimination_dehydration_001",
    "demethylation_aromatic_001", "decarboxylation_aromatic_001",
    "decarboxylation_beta_keto_001", "hydroxylation_aromatic_001",
    "hydration_alkene_001", "hydration_enone_001",
    "tautomerization_keto_enol_001", "esterification_gamma_lactone_001",
    "esterification_delta_lactone_001", "maillard_simplified_001",
]

# 化学意图对，但 SMARTS 还需调试（保留记录，不参与预测）
VERIFY = {
    "cyclization_hemiacetal_001":
        "★待调试★ 手工探针（4-羟基丁醛）也不匹配。环闭合产物模板可能有问题。"
        "化学意图正确（羟基醛成环，糖的呋喃/吡喃型），值得修。",
    "cyclization_lactam_001":
        "★待调试★ SMARTS 少了一个碳——γ-丁内酰胺是五元环，"
        "应为 [CX3:1](=[OX1:2])[CX4:3][CX4:4][CX4:5][NX3H2:6]，我只写了 2 个碳。",
    "condensation_aldol_intra_001":
        "★待调试★ 手工探针（5-氧代己醛、2,5-己二酮）都不匹配。",
    "elimination_decarboxylation_phenol_001":
        "★重复规则，已停用★ 手册探针（水杨酸/咖啡酸/没食子酸）全不匹配，"
        "而且化学上它和已有的「芳香酸脱羧」重复——后者的 SMARTS "
        "[c:1][CX3:2](=[OX1:3])[OX2H:4] 本来就匹配所有芳香羧酸（含酚酸）。"
        "留着只是为了记录这次判断。",
}

# 确认不可用
DISABLED = {
    "oxidation_thiol_disulfide_001":
        "★停用★ 成二硫需要两分子硫醇，而本引擎只支持单反应物规则。"
        "手工探针（半胱氨酸）也不匹配。这是引擎的结构性限制，不是 SMARTS 写错。",
    "isomerization_epimerization_001":
        "★停用★ SMARTS 两边完全相同，是恒等变换，不产生任何新分子。"
        "真正的差向异构需要立体化学模板，本引擎暂不支持。",
    "reduction_nitro_001":
        "★停用★ 校验器判 ATOM_CREATION（凭空造原子 H+3 O-2）。"
        "而且中药里硝基化合物罕见，不值得投入调试。",
}

data = json.loads(F.read_text(encoding="utf-8"))
changed = {"active": 0, "verify": 0, "disabled": 0}
unknown = []

for r in data["rules"]:
    rid = r["id"]
    if rid in ACTIVE:
        r["status"] = "active"
        changed["active"] += 1
    elif rid in VERIFY:
        r["status"] = "verify"
        r["notes"] = VERIFY[rid]
        r["priority"] = min(float(r.get("priority", 0.3)), 0.1)
        changed["verify"] += 1
    elif rid in DISABLED:
        r["status"] = "disabled"
        r["notes"] = DISABLED[rid]
        r["priority"] = 0.0
        changed["disabled"] += 1
    else:
        unknown.append(rid)

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"定稿：active {changed['active']} | verify {changed['verify']} "
      f"| disabled {changed['disabled']}")
if unknown:
    print(f"\n★未归类的 {len(unknown)} 条（状态未变）★")
    for u in unknown:
        print(f"   {u}")

from collections import Counter
c = Counter(r.get("status") for r in data["rules"])
print(f"\n规则总数 {len(data['rules'])}，状态分布：")
for k, v in c.most_common():
    print(f"   {k or '(无)':<10}{v}")
