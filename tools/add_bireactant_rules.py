# -*- coding: utf-8 -*-
"""追加双反应物规则：酯交换 / 酯化 / 席夫碱 / 酰胺化 / 酯的氨解。

这些规则对中药煎煮很关键，尤其是【酯交换】——
醇提（乙醇作溶剂）时乙醇会和药材里的酯生成新酯，这是醇提区别于水提的
化学本质之一，原来的单反应物引擎完全表达不了。

设计：
  · 第二个反应物从 co_substrate_pool 里取，池子受【条件】约束
    （醇提时才有乙醇，煎煮时只有水）
  · 双反应物规则走 rdkit 原生引擎 + !@ 环键约束
    （rdchiral 不支持多反应物；而这类反应断的通常是非环键）
"""
import json
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")

# 醇池：只在含醇的溶剂里提供
ALCOHOL_POOL = [
    {"smiles": "CCO", "name": "乙醇", "when_solvent": ["alcohol", "ethanol"]},
    {"smiles": "CO", "name": "甲醇", "when_solvent": ["alcohol", "ethanol", "methanol"]},
]
# 水
WATER_POOL = [
    {"smiles": "O", "name": "水", "when_solvent": ["water", "aqueous"]},
]
# 小分子胺池：来自氨基酸/生物碱等，不依赖溶剂
AMINE_POOL = [
    {"smiles": "N", "name": "氨"},
    {"smiles": "CN", "name": "甲胺"},
    {"smiles": "NCC(=O)O", "name": "甘氨酸"},
]

def R(rid, name, cat, smarts, profile, prio, limit, pool, notes):
    return {
        "id": rid, "name": name, "category": cat, "smarts": smarts,
        "reversible": True,
        "co_reagents": {}, "byproducts": {},
        "co_substrate_pool": pool,
        "condition_profile": profile, "priority": prio,
        "max_products_per_molecule": limit,
        "status": "draft",
        "notes": notes,
    }


NEW = [
    R("esterification_transesterification_001", "酯交换", "esterification",
      "[C:1](=[O:2])[O:3]!@[C:4].[OX2H:5][C:6]"
      ">>[C:1](=[O:2])[O:5][C:6].[O:3][C:4]",
      "hydrolysis", 0.55, 1, ALCOHOL_POOL + WATER_POOL,
      "★醇提的关键反应★ 乙醇与药材中的酯生成新酯。"
      "原来的单反应物引擎无法表达，这是本轮加双反应物支持的主要动机。"
      "!@ 约束断开的 C-O 键必须是非环键（环内酯另由单反应物规则处理）。"),

    R("esterification_intermolecular_001", "酯化(分子间)", "esterification",
      "[CX3:1](=[OX1:2])[OX2H:3].[OX2H:4][#6:5]"
      ">>[C:1](=[O:2])[O:4][#6:5].[OH2:3]",
      "thermal", 0.45, 1, ALCOHOL_POOL,
      "有机酸 + 醇 → 酯 + 水。与已有的分子内酯化（内酯化）互补。"),

    R("condensation_schiff_base_001", "席夫碱生成", "condensation",
      "[CX3H1:1]=[OX1:2].[NX3H2:3][#6:4]"
      ">>[C:1]=[N:3][#6:4].[OH2:2]",
      "ambient", 0.35, 2, AMINE_POOL,
      "醛 + 伯胺 → 亚胺 + 水。美拉德反应的前期步骤之一。"),

    R("amidation_intermolecular_001", "酰胺化(分子间)", "condensation",
      "[CX3:1](=[OX1:2])[OX2H:3].[NX3H2:4][#6:5]"
      ">>[C:1](=[O:2])[N:4][#6:5].[OH2:3]",
      "thermal", 0.3, 1, AMINE_POOL,
      "有机酸 + 胺 → 酰胺 + 水。中性水中很慢，条件层应压制。"),

    R("aminolysis_ester_001", "酯的氨解", "condensation",
      "[C:1](=[O:2])[O:3]!@[C:4].[NX3H2:5][#6:6]"
      ">>[C:1](=[O:2])[N:5][#6:6].[O:3][C:4]",
      "ambient", 0.3, 1, AMINE_POOL,
      "酯 + 胺 → 酰胺 + 醇。生物碱与氨基酸共存时可能发生。"),
]

data = json.loads(F.read_text(encoding="utf-8"))
existing = {r["id"] for r in data["rules"]}
added = []
for r in NEW:
    if r["id"] in existing:
        print(f"跳过已存在: {r['id']}")
        continue
    data["rules"].append(r)
    added.append(f"{r['name']:<18} {r['id']}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"新增 {len(added)} 条双反应物规则：")
for a in added:
    print("   " + a)
print(f"\n规则总数：{len(data['rules'])}")
