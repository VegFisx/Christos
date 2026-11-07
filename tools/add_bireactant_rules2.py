# -*- coding: utf-8 -*-
"""第二批双反应物规则：把规则库推向 60 条。

覆盖中药化学里另外几类核心的成键反应：
  · 糖苷化   —— 糖的端基羟基与醇/酚成苷
  · 半缩醛   —— 醛 + 醇，缩醛/糖苷的第一步
  · Michael 加成（硫醇/胺）—— 多酚-蛋白结合、生物碱加成的化学基础
  · 醇醛缩合 —— 碳碳成键，糖降解产物之间
  · 硫代半缩醛 —— 含硫成分与醛的结合

设计沿用上一轮：第二个反应物从 co_substrate_pool 取，池子受条件约束。
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")

ALCOHOL_POOL = [
    {"smiles": "CCO", "name": "乙醇", "when_solvent": ["alcohol", "ethanol"]},
    {"smiles": "CO", "name": "甲醇", "when_solvent": ["alcohol", "ethanol", "methanol"]},
    {"smiles": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
     "name": "葡萄糖", "when_solvent": ["water", "aqueous", "alcohol", "ethanol"]},
]
THIOL_POOL = [
    {"smiles": "CS", "name": "甲硫醇"},
    {"smiles": "NC(CS)C(=O)O", "name": "半胱氨酸"},
]
AMINE_POOL = [
    {"smiles": "N", "name": "氨"},
    {"smiles": "CN", "name": "甲胺"},
    {"smiles": "NCC(=O)O", "name": "甘氨酸"},
]
# 醛类：糖降解产物、美拉德中间体
ALDEHYDE_POOL = [
    {"smiles": "C=O", "name": "甲醛"},
    {"smiles": "CC=O", "name": "乙醛"},
]


def R(rid, name, cat, smarts, profile, prio, limit, pool, notes, rev=True):
    return {
        "id": rid, "name": name, "category": cat, "smarts": smarts,
        "reversible": rev,
        "co_reagents": {}, "byproducts": {},
        "co_substrate_pool": pool,
        "condition_profile": profile, "priority": prio,
        "max_products_per_molecule": limit,
        "status": "draft",
        "notes": notes,
    }


NEW = [
    R("condensation_glycosylation_001", "糖苷化", "condensation",
      "[CX4H1:1]([OX2:3][#6:4])[OX2H:2].[OX2H:5][#6:6]"
      ">>[CX4H1:1]([OX2:3][#6:4])[O:5][#6:6].[OH2:2]",
      "hydrolysis", 0.4, 1, ALCOHOL_POOL,
      "糖的端基羟基（半缩醛碳 [CX4H1](O)(OR)）与另一个醇成苷，脱一分子水。"
      "★要求第一个反应物本身就是半缩醛（糖环），所以不会把普通醇也配上去。"
      "这是水解的逆反应，与「糖苷水解」成对。"),

    R("condensation_hemiacetal_001", "半缩醛形成(分子间)", "condensation",
      "[CX3H1:1]=[OX1:2].[OX2H:3][#6:4]>>[CX4H1:1]([OH:2])[O:3][#6:4]",
      "ambient", 0.4, 1, ALCOHOL_POOL,
      "醛 + 醇 → 半缩醛。缩醛/糖苷形成的第一步，不加不减原子。"),

    R("addition_michael_thiol_001", "Michael加成(硫醇)", "addition",
      "[C:1]=[C:2][C:3]=[OX1:4].[SX2H:5]"
      ">>[CX4:1][CX4:2]([S:5])[C:3]=[OX1:4]",
      "ambient", 0.35, 1, THIOL_POOL,
      "α,β-不饱和羰基 + 硫醇 → β-硫代羰基。"
      "多酚与蛋白质结合、含硫成分加成的化学基础。"
      "硫醇用 [SX2H] 描述（硫上带 1 个氢），这是 RDKit 匹配硫醇的标准写法，"
      "写 [S][H] 会因为大多数 SMILES 不含显式氢而匹配不上。"),

    R("addition_michael_amine_001", "Michael加成(胺)", "addition",
      "[C:1]=[C:2][C:3]=[OX1:4].[NX3H2:5][#6:6]"
      ">>[CX4:1][CX4:2]([N:5][#6:6])[C:3]=[OX1:4]",
      "ambient", 0.3, 1, AMINE_POOL,
      "α,β-不饱和羰基 + 伯胺 → β-氨基羰基。生物碱与烯酮类成分的加成。"),

    R("condensation_aldol_001", "醇醛缩合(分子间)", "condensation",
      "[CX3:1](=[OX1:2])[CX4H2:3].[CX3:4](=[OX1:5])[#6:6]"
      ">>[C:1](=[O:2])[C:3][C:4]([OH:5])[#6:6]",
      "ambient", 0.3, 1, ALDEHYDE_POOL,
      "碳碳成键。含 α-H 的羰基进攻另一个羰基，生成 β-羟基羰基。"
      "糖降解产生的小醛之间可能发生。"),

    R("addition_thiohemiacetal_001", "硫代半缩醛形成", "addition",
      "[CX3H1:1]=[OX1:2].[SX2H:3][#6:4]>>[CX4H1:1]([OH:2])[S:3][#6:4]",
      "ambient", 0.3, 1, THIOL_POOL,
      "醛 + 硫醇 → 硫代半缩醛。含硫成分（大蒜素类）与醛的结合。"),
]

data = json.loads(F.read_text(encoding="utf-8"))
existing = {r["id"] for r in data["rules"]}
added = []
for r in NEW:
    if r["id"] in existing:
        print(f"跳过已存在: {r['id']}")
        continue
    data["rules"].append(r)
    added.append(f"{r['name']:<22} {r['id']}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"新增 {len(added)} 条：")
for a in added:
    print("   " + a)
print(f"\n规则总数：{len(data['rules'])}")
