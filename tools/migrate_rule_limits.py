# -*- coding: utf-8 -*-
"""把原 tcm_analyzer.py 里的 RULE_LIMITS 迁移到新规则库的 max_products_per_molecule。

原字典（作者逐条调过的产物数上限）：
    "羟基氧化": 2, "脱甲基": 2, "芳香环羟基化": 1, "芳香酸脱羧": 1,
    "酮还原": 1, "醌还原": 2, "缩醛水解": 1, "半缩醛水解": 2,
    "酚氧化成醌": 1, "胺氧化": 2, "酮-烯醇化": 1, "β-酮酸脱羧": 2,
    "糖苷水解": 3, "酯水解": 3, "酰胺水解": 3, "硫酸酯水解": 3,
    "磷酸酯水解": 3, "脱水": 3, "醛氧化": 3, "烯烃水合": 1,
    "α,β-不饱和羰基水合": 1, "酯化": 2, "美拉德简化": 3,
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")

# 中文规则名 → 新规则 id
NAME_TO_ID = {
    "酯水解": "hydrolysis_ester_001",
    "糖苷水解": "hydrolysis_glycoside_001",
    "酰胺水解": "hydrolysis_amide_001",
    "硫酸酯水解": "hydrolysis_sulfate_001",
    "磷酸酯水解": "hydrolysis_phosphate_001",
    "缩醛水解": "hydrolysis_acetal_001",
    "半缩醛水解": "hydrolysis_hemiacetal_001",
    "羟基氧化": "oxidation_hydroxyl_001",
    "醛氧化": "oxidation_aldehyde_001",
    "酚氧化成醌": "oxidation_phenol_quinone_001",
    "胺氧化": "oxidation_amine_001",
    "酮还原": "reduction_ketone_001",
    "醌还原": "reduction_quinone_001",
    "脱水": "elimination_dehydration_001",
    "脱甲基": "demethylation_aromatic_001",
    "芳香酸脱羧": "decarboxylation_aromatic_001",
    "β-酮酸脱羧": "decarboxylation_beta_keto_001",
    "芳香环羟基化": "hydroxylation_aromatic_001",
    "烯烃水合": "hydration_alkene_001",
    "α,β-不饱和羰基水合": "hydration_enone_001",
    "酮-烯醇化": "tautomerization_keto_enol_001",
    "美拉德简化": "maillard_simplified_001",
    # 原「酯化」一条坏的，已被 γ-内酯化 / δ-内酯化 两条取代，上限照搬
    "酯化": "esterification_gamma_lactone_001",
}

RULE_LIMITS = {
    "羟基氧化": 2, "脱甲基": 2, "芳香环羟基化": 1, "芳香酸脱羧": 1,
    "酮还原": 1, "醌还原": 2, "缩醛水解": 1, "半缩醛水解": 2,
    "酚氧化成醌": 1, "胺氧化": 2, "酮-烯醇化": 1, "β-酮酸脱羧": 2,
    "糖苷水解": 3, "酯水解": 3, "酰胺水解": 3, "硫酸酯水解": 3,
    "磷酸酯水解": 3, "脱水": 3, "醛氧化": 3, "烯烃水合": 1,
    "α,β-不饱和羰基水合": 1, "酯化": 2, "美拉德简化": 3,
}

# 反向：id → 上限
ID_TO_LIMIT = {NAME_TO_ID[n]: v for n, v in RULE_LIMITS.items() if n in NAME_TO_ID}
# δ-内酯化 也照搬原来「酯化」的上限
ID_TO_LIMIT["esterification_delta_lactone_001"] = RULE_LIMITS["酯化"]

data = json.loads(F.read_text(encoding="utf-8"))

# δ-内酯化 与 γ-内酯化 本来就自带 2，保留
applied, missing = [], []
for r in data["rules"]:
    rid = r["id"]
    if rid in ID_TO_LIMIT:
        r["max_products_per_molecule"] = ID_TO_LIMIT[rid]
        applied.append(f"{r['name']:<20} {rid:<38} 上限 {ID_TO_LIMIT[rid]}")
    else:
        missing.append(f"{r['name']:<20} {rid}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"已迁移上限 {len(applied)} 条：")
for a in applied:
    print("   " + a)
if missing:
    print(f"\n未设上限 {len(missing)} 条（原 RULE_LIMITS 里也没有）：")
    for m in missing:
        print("   " + m)
print(f"\n规则总数: {len(data['rules'])}")
