# -*- coding: utf-8 -*-
"""修 2 条 verify 规则 + 再补 4 条单反应物规则，把规则库推过 60。

修错：
  · 分子内半缩醛化：环上的氧写错了。环里应该是【羟基的氧】(O6)，
    我写成了【醛基的氧】(O2)——等于说醛的氧既在环里又是羟基，化学上说不通。
  · 分子内酰胺化：少了一个碳。γ-丁内酰胺是五元环（C=O + 3×CH2 + N），
    我只写了 2 个 CH2。

停用：
  · 分子内羟醛缩合：SMARTS 里 C3 与 C4 本来就成键，再让它们成键没有意义。
    真正的分子内醇醛需要 1,5- 或 1,6-二羰基，得重写。
  · 酚酸脱羧成酚：与已有的「芳香酸脱羧」重复。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")
data = json.loads(F.read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data["rules"]}

FIXES = {
    "cyclization_hemiacetal_001": {
        "smarts": ("[CX3H1:1]=[OX1:2][CX4:3][CX4:4][CX4:5][OX2H:6]"
                   ">>[C:1]1([OH:2])[CX4:3][CX4:4][CX4:5][O:6]1"),
        "co_reagents": {}, "byproducts": {},
        "status": "draft",
        "priority": 0.5,
        "notes": ("★已修★ 环上的氧写错了：原产物写成 [C:1]1([OH:6])[...][O:2]1，"
                  "等于让醛基的氧既在环里又是羟基。正确应是【羟基的氧 O6】进环，"
                  "醛基的氧 O2 变成羟基——这正是半缩醛的化学。"
                  "实证：4-羟基丁醛 → 2-羟基四氢呋喃。"),
    },
    "cyclization_lactam_001": {
        "smarts": ("[CX3:1](=[OX1:2])[CX4:3][CX4:4][CX4:5][NX3H2:6]"
                   ">>[C:1]1(=[O:2])[CX4:3][CX4:4][CX4:5][N:6]1"),
        "co_reagents": {}, "byproducts": {},
        "status": "draft",
        "priority": 0.4,
        "notes": ("★已修★ 原 SMARTS 少了一个碳——γ-丁内酰胺是五元环"
                  "（C=O + 3 个 CH2 + N），我只写了 2 个 CH2，"
                  "所以连 4-氨基丁酸都匹配不上。现已补齐。"),
    },
}

DISABLE = {
    "condensation_aldol_intra_001":
        "★停用★ SMARTS 里 [CX4H2:3] 与 [CX3:4] 本来就成键，再让它们成键没有意义。"
        "真正的分子内醇醛需要 1,5- 或 1,6-二羰基（两端羰基之间隔着 ≥2 个碳）。"
        "与其硬凑，不如停用——分子间醇醛（condensation_aldol_001）已经覆盖了碳碳成键。",
    "elimination_decarboxylation_phenol_001":
        "★停用★ 与已有的「芳香酸脱羧」重复：后者的 SMARTS [c:1][CX3:2](=[OX1:3])[OX2H:4] "
        "本来就匹配所有芳香羧酸（含酚酸）。手工探针（水杨酸/咖啡酸/没食子酸）全不匹配。",
}

NEW = [
    {
        "id": "elimination_amide_to_nitrile_001",
        "name": "酰胺脱水成腈", "category": "elimination",
        "smarts": "[CX3:1](=[OX1:2])[NX3H2:3]>>[C:1]#[N:3]",
        "reversible": False, "co_reagents": {}, "byproducts": {},
        "condition_profile": "thermal", "priority": 0.3,
        "max_products_per_molecule": 1, "status": "draft",
        "notes": "高温脱水。乙酰胺 → 乙腈 + 水。中药煎煮温度下较慢，权重压低。",
    },
    {
        "id": "oxidation_sulfoxide_to_sulfone_001",
        "name": "亚砜氧化成砜", "category": "oxidation",
        "smarts": "[#6:1][S:2](=[OX1:3])[#6:4]>>[#6:1][S:2](=[OX1:3])(=[O])[#6:4]",
        "reversible": False, "co_reagents": {}, "byproducts": {},
        "condition_profile": "oxidation", "priority": 0.3,
        "max_products_per_molecule": 1, "status": "draft",
        "notes": "含硫成分深度氧化（大蒜素类）。与「硫醚氧化成亚砜」接力。",
    },
    {
        "id": "reduction_sulfoxide_001",
        "name": "亚砜还原成硫醚", "category": "reduction",
        "smarts": "[#6:1][S:2](=[OX1:3])[#6:4]>>[#6:1][S:2][#6:4]",
        "reversible": True, "co_reagents": {}, "byproducts": {},
        "condition_profile": "reduction", "priority": 0.3,
        "max_products_per_molecule": 1, "status": "draft",
        "notes": "DMSO → DMS 型还原，只在通氢条件下发生（条件层靠 atmosphere 关掉）。",
    },
    {
        "id": "decarboxylation_cinnamic_001",
        "name": "肉桂酸型脱羧", "category": "decarboxylation",
        "smarts": ("[c:1][CX3H:2]=[CX3H:3][CX3:4](=[OX1:5])[OX2H:6]"
                   ">>[c:1][CX3H:2]=[CX3:3].[C](=[O])=[O]"),
        "reversible": False, "co_reagents": {}, "byproducts": {},
        "condition_profile": "thermal", "priority": 0.5,
        "max_products_per_molecule": 1, "status": "draft",
        "notes": ("肉桂酸 / 咖啡酸 / 阿魏酸型脱羧，生成对应的乙烯基酚（如 4-乙烯基苯酚）。"
                  "★与「芳香酸脱羧」不同：那个断的是芳环上的羧基，这个断的是侧链烯酸，"
                  "产物是苯乙烯型而不是苯型——两者产物完全不同，不是重复规则。"),
    },
]

n_fix = n_dis = n_new = 0
for rid, patch in FIXES.items():
    if rid in by_id:
        by_id[rid].update(patch)
        n_fix += 1
        print(f"[修] {by_id[rid]['name']}")
        print(f"     新 SMARTS: {patch['smarts']}")

for rid, why in DISABLE.items():
    if rid in by_id:
        by_id[rid]["status"] = "disabled"
        by_id[rid]["priority"] = 0.0
        by_id[rid]["notes"] = why
        n_dis += 1
        print(f"[停用] {by_id[rid]['name']}")

for r in NEW:
    if r["id"] in by_id:
        print(f"[跳过] {r['id']} 已存在")
        continue
    data["rules"].append(r)
    n_new += 1
    print(f"[新增] {r['name']:<18} {r['id']}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"\n修 {n_fix} 条 / 停用 {n_dis} 条 / 新增 {n_new} 条")
print(f"规则总数：{len(data['rules'])}")
