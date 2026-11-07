# -*- coding: utf-8 -*-
"""批量写入新规则草稿。

工作流：
  1. 本脚本把新规则以 status="draft"、co_reagents/byproducts 为空追加进 rules.json
  2. tools/derive_co_reagents.py --apply  自动推导陪跑试剂
  3. rules/schema.py  校验（原子守恒 + 静态检查）
  4. 通过的把 status 改成 "active"

这样写规则就不靠人肉推配平了——推错会被工具当场抓住。
"""
import json
import sys
from pathlib import Path

F = Path(r"D:\ProgramData\DSHNS\chemreact-staging\rules\rules.json")

# 统一给个条件窗口与优先级，随后再按需微调
def R(rid, name, cat, smarts, profile, prio, limit, notes="", rev=False):
    return {
        "id": rid, "name": name, "category": cat, "smarts": smarts,
        "reversible": rev,
        "co_reagents": {}, "byproducts": {},
        "condition_profile": profile, "priority": prio,
        "max_products_per_molecule": limit,
        "status": "draft",
        "notes": notes or "新规则草稿，陪跑试剂待自动推导",
    }


CANDIDATES = [
    # ---------------- 氧化（补 5 条）----------------
    R("oxidation_primary_alcohol_001", "伯醇氧化成醛", "oxidation",
      "[CX4H2:1][OH:2]>>[C:1]=[O:2]", "oxidation", 0.55, 2,
      "与「羟基氧化」(仲醇→酮) 互补：这个是伯醇→醛。"),
    R("oxidation_sulfide_001", "硫醚氧化成亚砜", "oxidation",
      "[#6:1][S:2][#6:3]>>[#6:1][S:2](=[O])[#6:3]", "oxidation", 0.4, 1,
      "大蒜素等含硫成分的氧化。"),
    R("oxidation_epoxide_001", "双键环氧化", "oxidation",
      "[C:1]=[C:2]>>[C:1]1[O][C:2]1", "oxidation", 0.35, 1,
      "无区域选择性，仅限流 1 个。萜类双键易被氧化。"),
    R("oxidation_dehydrogenation_enone_001", "脱氢成α,β-不饱和羰基", "oxidation",
      "[CX4:1][CX4:2][CX3:3]=[OX1:4]>>[C:1]=[C:2][C:3]=[OX1:4]",
      "oxidation", 0.4, 1, "形成共轭烯酮，热力学有利。"),
    R("oxidation_thiol_disulfide_001", "硫醇偶联成二硫", "oxidation",
      "[S:1][H]>>[S:1]", "oxidation", 0.3, 1,
      "★注意★ 这个 SMARTS 只能表达单个硫醇的变化，成二硫需要两分子，"
      "而本引擎只支持单反应物规则。列入草稿是为了标记缺口，预计校验会判它不平衡。"),

    # ---------------- 还原（补 3 条）----------------
    R("reduction_aldehyde_001", "醛还原成醇", "reduction",
      "[CX3H1:1]=[OX1:2]>>[CX4:1][OH:2]", "reduction", 0.4, 2),
    R("reduction_alkene_001", "双键加氢", "reduction",
      "[C:1]=[C:2]>>[C:1][C:2]", "reduction", 0.35, 1,
      "过宽，仅限流 1 个；实际只在强还原条件下发生。"),
    R("reduction_nitro_001", "硝基还原成胺", "reduction",
      "[NX3:1](=[OX1:2])[OX1:3]>>[NX3:1]", "reduction", 0.3, 1,
      "中药中硝基化合物罕见，保留以备用。"),

    # ---------------- 开环水解（补 3 条）----------------
    R("hydrolysis_epoxide_001", "环氧化物开环成二醇", "hydrolysis",
      "[C:1]1[OX2:2][C:3]1>>[C:1]([OH:2])[C:3][OH]", "hydrolysis", 0.6,
      1, "rdchiral 可正确处理环内断键，这正是它相对 rdkit 的优势。"),
    R("hydrolysis_lactam_001", "内酰胺开环", "hydrolysis",
      "[CX3:1](=[OX1:2])[NX3:3][CX4:4]>>[C:1](=[O:2])[OH].[N:3][CX4:4]",
      "hydrolysis", 0.4, 1, "环内断键，靠 rdchiral。"),
    R("hydrolysis_imine_001", "亚胺水解", "hydrolysis",
      "[CX3H1:1]=[NX2:2][#6:3]>>[C:1]=[O].[N:2][#6:3]", "hydrolysis", 0.5,
      1, "生成的醛需不编号的 [O]。"),

    # ---------------- 环化 / 缩合（补 5 条）----------------
    R("cyclization_hemiacetal_001", "分子内半缩醛化", "cyclization",
      "[CX3H1:1]=[OX1:2][CX4:3][CX4:4][CX4:5][OX2H:6]"
      ">>[C:1]1([OH:6])[CX4:3][CX4:4][CX4:5][O:2]1",
      "ambient", 0.5, 1, "羟基醛成环（如糖的呋喃型/吡喃型）。"),
    R("cyclization_lactam_001", "分子内酰胺化", "cyclization",
      "[CX3:1](=[OX1:2])[CX4:3][CX4:4][NX3H2:5]"
      ">>[C:1]1(=[O:2])[CX4:3][CX4:4][N:5]1",
      "thermal", 0.4, 1, "氨基酸成内酰胺，脱水。"),
    R("cyclization_ether_001", "分子内脱水成醚", "cyclization",
      "[OX2H:1][CX4:2][CX4:3][CX4:4][OX2H:5]"
      ">>[O:1]1[CX4:2][CX4:3][CX4:4][O:5]1",
      "thermal", 0.3, 1, "二醇成环醚（四氢呋喃型）。"),
    R("cyclization_lactone_delta_001", "δ-羟基酸内酯化(备用)", "cyclization",
      "[OX2H:1][CX4:2][CX4:3][CX4:4][CX4:5][CX3:6](=[OX1:7])[OX2H:8]"
      ">>[O:1]1[CX4:2][CX4:3][CX4:4][CX4:5][CX3:6]1=[OX1:7].[OH2:8]",
      "thermal", 0.45, 1,
      "与已有 δ-内酯化 编号方式不同，用于交叉验证写法是否稳健。"),
    R("condensation_aldol_intra_001", "分子内羟醛缩合", "condensation",
      "[CX3H1:1]=[OX1:2][CX4H2:3][CX3:4]=[OX1:5]"
      ">>[C:1]1([OH:2])[CX4H:3][C:4](=[OX1:5])1",
      "ambient", 0.35, 1, "1,4-二羰基分子内成环。"),

    # ---------------- 异构 / 重排（补 3 条）----------------
    R("isomerization_double_bond_001", "双键位置异构", "rearrangement",
      "[CX4:1][CX3:2]=[CX3:3][CX4:4]>>[CX3:1]=[CX3:2][CX4:3][CX4:4]",
      "thermal", 0.3, 1, "双键沿链迁移，趋向共轭。"),
    R("isomerization_epimerization_001", "差向异构化", "rearrangement",
      "[CX4H1:1]([OH:2])[CX4:3]>>[CX4H1:1]([OH:2])[CX4:3]",
      "ambient", 0.25, 1,
      "★注★ SMARTS 两边一样，是恒等变换；真正的差向异构需要立体化学模板，"
      "本引擎暂不支持。列入草稿是为了标记缺口。"),
    R("rearrangement_retro_aldol_001", "逆羟醛裂解", "rearrangement",
      "[C:1]([OH:2])[CX4H:3][C:4](=[OX1:5])>>[CX3:1]=[OX1:2].[CX3:3][C:4](=[OX1:5])",
      "thermal", 0.3, 1, "碳碳键断裂，生成两个片段。"),

    # ---------------- 脱羧 / 脱氨（补 3 条）----------------
    R("decarboxylation_malonic_001", "丙二酸型脱羧", "decarboxylation",
      "[CX3:1](=[OX1:2])[CX4:3][CX3:4](=[OX1:5])[OX2H:6]"
      ">>[CX3:1](=[OX1:2])[CX4:3].[C](=[O])=[O]",
      "thermal", 0.6, 1, "与 β-酮酸脱羧同型，用于交叉验证。"),
    R("elimination_deamination_001", "氧化脱氨成羰基", "elimination",
      "[CX4H2:1][NX3H2:2]>>[CX3H1:1]=[O].[N:2]",
      "oxidation", 0.35, 1, "与已有「胺氧化」同型，用于交叉验证。"),
    R("elimination_decarboxylation_phenol_001", "酚酸脱羧成酚", "decarboxylation",
      "[OH:1][c:2][c:3]([CX3:4](=[OX1:5])[OX2H:6])[cH:7]"
      ">>[OH:1][c:2][c:3][H].[C](=[O])=[O]",
      "thermal", 0.55, 1,
      "咖啡酸→乙烯基儿茶酚类转化，中药煎煮常见。"),
]

data = json.loads(F.read_text(encoding="utf-8"))
existing = {r["id"] for r in data["rules"]}
added, skipped = [], []
for c in CANDIDATES:
    if c["id"] in existing:
        skipped.append(c["id"])
        continue
    data["rules"].append(c)
    added.append(f"{c['name']:<22} {c['id']}")

F.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"新增 {len(added)} 条草稿：")
for a in added:
    print("   " + a)
if skipped:
    print(f"\n跳过已存在的 {len(skipped)} 条：{skipped}")
print(f"\n规则总数：{len(data['rules'])}")
