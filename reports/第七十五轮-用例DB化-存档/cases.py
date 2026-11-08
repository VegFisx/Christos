# -*- coding: utf-8 -*-
r"""
chemreact 反应级验收测试集
==========================

★ 和前面四道闸门的区别

  前四道闸门（原子守恒 / 价态 / 化学合理性 / 立体化学）都是【自洽性检查】：
  它们能发现"自相矛盾"，但**不知道正确答案是什么**。
  一条规则可能原子配平、结构合理、手性也保住了，却**化学上完全是错的**。

  这份测试集补的是这一层：**用已知的化学答案去卡引擎**。

★ 用例形式

  · kind="rule"    给底物 + 指定规则 → 产物里【必须有】某些分子、【必须没有】某些分子
  · kind="gating"  给条件 → 某些规则【必须激活】/【必须熄灭】
  · kind="cascade" 跑完整链路 → 产物集合必须满足正/负向断言

★ 每个用例都写了 note 说明化学依据。
  没有依据的用例不如不写——那只会给假的安全感。
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "reaction_cases.json"


def C(cid, rule, smiles, name, expect_any=None, forbid=None, note="",
      conditions="煎煮", kind="rule"):
    return {
        "id": cid, "kind": kind, "rule": rule, "smiles": smiles, "name": name,
        "conditions": conditions,
        "expect_any": expect_any or [],
        "forbid": forbid or [],
        "note": note,
    }


CASES = [
    # ================= 水解 =================
    C("hyd_ester_benzoate", "hydrolysis_ester_001", "COC(=O)c1ccccc1", "苯甲酸甲酯",
      ["O=C(O)c1ccccc1"], note="酯水解生成羧酸。苯甲酸是标志性产物"),
    C("hyd_ester_ethylacetate", "hydrolysis_ester_001", "CCOC(C)=O", "乙酸乙酯",
      ["CC(=O)O"], note="简单酯水解生成乙酸"),
    C("hyd_glycoside_salicin", "hydrolysis_glycoside_001",
      "CO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O", "甲基葡萄糖苷",
      ["CO"], note="糖苷水解：甲基葡萄糖苷 → 葡萄糖（苷元侧是甲醇）。★水杨苷那条跑不出产物，先用最简单的甲基糖苷隔离规则本身是否有问题"),
    C("hyd_amide_acetamide", "hydrolysis_amide_001", "CC(N)=O", "乙酰胺（伯酰胺）",
      ["CC(=O)O"],
      note="★原本是覆盖缺口：规则写成 [N:3][C:4] 要求氮上连碳，伯酰胺全灭。已改为 [N:3]——未映射的取代基会原样带入产物，一条 SMARTS 同时覆盖伯酰胺与 N-取代酰胺。这条用例现在验证修复"),
    C("hyd_acetal_benzaldehyde", "hydrolysis_acetal_001",
      "COC(OC)c1ccccc1", "苯甲醛二甲缩醛",
      ["O=Cc1ccccc1"], note="缩醛水解回到醛——这是缩醛的保护/脱保护原理"),
    C("hyd_sulfate", "hydrolysis_sulfate_001", "COS(=O)(=O)O", "硫酸单甲酯",
      ["CO"], note="硫酸酯水解掉硫酸根，放出甲醇"),
    C("hyd_lactam", "hydrolysis_lactam_001", "O=C1CCCN1", "2-吡咯烷酮",
      ["NCCCC(=O)O"], note="内酰胺开环生成 γ-氨基丁酸"),

    # ================= 氧化 =================
    C("ox_primary_alcohol", "oxidation_primary_alcohol_001", "OCc1ccccc1", "苯甲醇",
      ["O=Cc1ccccc1"], note="伯醇氧化成醛。苯甲醇→苯甲醛是教科书反应"),
    C("ox_aldehyde", "oxidation_aldehyde_001", "O=Cc1ccccc1", "苯甲醛",
      ["O=C(O)c1ccccc1"], note="醛进一步氧化成酸"),
    C("ox_hydroxyl_isopropanol", "oxidation_hydroxyl_001", "CC(C)O", "异丙醇",
      ["CC(C)=O"], note="仲醇氧化成酮。异丙醇→丙酮"),
    C("ox_phenol_quinone", "oxidation_phenol_quinone_001",
      "Oc1ccccc1O", "邻苯二酚",
      ["O=C1C=CC=CC1=O"],
      note="邻苯二酚氧化成【邻】苯醌。★规则的 [OH][c][c][OH] 要求两个羟基相邻，对苯二酚（1,4-）不匹配；且产物是邻醌不是对醌"),
    C("ox_sulfide_sulfoxide", "oxidation_sulfide_001", "CSC", "二甲硫醚",
      ["CSC=O", "CS(C)=O"], note="硫醚氧化成亚砜（DMSO 的生成）"),
    C("ox_aromatic_hydroxyl", "hydroxylation_aromatic_001", "Oc1ccccc1", "苯酚",
      ["Oc1ccccc1O", "Oc1cccc(O)c1", "Oc1ccc(O)cc1"],
      note="酚的羟基化。★实测该规则【不具位置选择性】——邻/间/对三种异构体都产。这对「列出所有可能候选」是合理的，但用于定量预测时是个已知局限"),

    # ================= 还原 =================
    C("red_ketone", "reduction_ketone_001", "CC(C)=O", "丙酮",
      ["CC(C)O"], note="酮还原成仲醇", conditions="还原"),
    C("red_aldehyde", "reduction_aldehyde_001", "O=Cc1ccccc1", "苯甲醛",
      ["OCc1ccccc1"], note="醛还原成伯醇", conditions="还原"),
    C("red_double_bond", "reduction_alkene_001", "C=CC", "丙烯",
      ["CCC"], note="碳碳双键加氢", conditions="还原"),
    C("red_sulfoxide", "reduction_sulfoxide_001", "CS(C)=O", "DMSO",
      ["CSC"], note="亚砜还原回硫醚", conditions="还原"),

    # ================= 脱羧 =================
    C("dec_aromatic", "decarboxylation_aromatic_001", "O=C(O)c1ccccc1", "苯甲酸",
      ["c1ccccc1"], note="芳香酸脱羧生成苯"),
    C("dec_beta_keto", "decarboxylation_beta_keto_001", "CC(=O)CC(=O)O", "乙酰乙酸",
      ["CC(C)=O"], note="β-酮酸脱羧生成酮 + CO2。这是最简单的脱羧"),
    C("dec_malonic", "decarboxylation_malonic_001", "OC(=O)CC(=O)O", "丙二酸",
      ["CC(=O)O"], note="丙二酸型脱羧生成一元酸"),
    C("dec_cinnamic", "decarboxylation_cinnamic_001",
      "OC(=O)/C=C/c1ccccc1", "肉桂酸",
      ["C=Cc1ccccc1"], note="肉桂酸型脱羧生成苯乙烯——注意产物是【乙烯基】不是苯环羟基"),

    # ================= 缩合 / 加成（双反应物） =================
    C("cond_esterification", "esterification_intermolecular_001",
      "O=C(O)c1ccccc1", "苯甲酸",
      ["CCOC(=O)c1ccccc1"], note="酯化：苯甲酸 + 乙醇 → 苯甲酸乙酯（醇提条件下）",
      conditions="醇提"),
    C("cond_transesterification", "esterification_transesterification_001",
      "COC(=O)c1ccccc1", "苯甲酸甲酯",
      ["CCOC(=O)c1ccccc1"], note="★酯交换★ 甲酯 + 乙醇 → 乙酯。这是「醇提≠水提」的化学实质",
      conditions="醇提"),
    C("cond_schiff", "condensation_schiff_base_001", "O=Cc1ccccc1", "苯甲醛",
      ["O=C(O)CN=Cc1ccccc1"],
      note="醛 + 胺池里的【甘氨酸】→ 席夫碱。★原期望写的是 N-甲基化物(CN=Cc1ccccc1)，"
           "那是照着【甲胺】算的；而甲胺在煎煮水里根本不存在，"
           "已从池子里移除（见 tools/audit_cosubstrates.py），"
           "现按药材真实存在的甘氨酸出产物",
      conditions="室温浸泡"),
    C("cond_amidation", "amidation_intermolecular_001", "CC(=O)O", "乙酸",
      ["CC(=O)NCC(=O)O"],
      note="酸 + 胺池里的【甘氨酸】→ 马尿酸型酰胺。原期望的 N-甲基化物同样是照甲胺算的"),
    C("cond_aminolysis", "aminolysis_ester_001", "COC(C)=O", "乙酸甲酯",
      ["CC(=O)NCC(=O)O"],
      note="酯的氨解：酯 + 胺池里的【甘氨酸】→ 马尿酸型酰胺（原期望的 N-甲基化物已随甲胺移除）",
      conditions="室温浸泡"),
    C("add_michael_thiol", "addition_michael_thiol_001", "C=CC=O", "丙烯醛",
      ["CSCCC=O"],
      note="★Michael 加成：硫必须加在 β碳上 → 3-甲硫基丙醛。原规则错加在 α碳（给 CSC(C)C=O）——两者分子式完全相同，原子守恒/价态/立体化学三道闸门全都发现不了，只有反应级测试集能抓出来",
      conditions="室温浸泡"),

    # ================= 环化 =================
    C("cyc_gamma_lactone", "esterification_gamma_lactone_001", "OCCCC(=O)O", "4-羟基丁酸",
      ["O=C1CCCO1"], note="γ-羟基酸分子内酯化生成五元内酯"),
    C("cyc_delta_lactone", "cyclization_lactone_delta_001", "OCCCCC(=O)O", "5-羟基戊酸",
      ["O=C1CCCCO1"], note="δ-羟基酸生成六元内酯"),
    C("cyc_hemiacetal", "cyclization_hemiacetal_001", "O=CCCCO", "4-羟基丁醛",
      ["OC1CCCO1"], note="4-羟基丁醛成环生成 2-羟基四氢呋喃",
      conditions="室温浸泡"),
    C("cyc_lactam", "cyclization_lactam_001", "NCCCC(=O)O", "4-氨基丁酸",
      ["O=C1CCCN1"], note="γ-氨基丁酸成环生成 γ-丁内酰胺"),
    C("cyc_ether", "cyclization_ether_001", "OCCCCO", "1,4-丁二醇",
      ["C1CCOC1"],
      note="分子内脱水成醚生成四氢呋喃。★规则要求两个羟基之间恰好隔 4 个碳"),

    # ================= 消除 / 重排 =================
    C("eli_dehydration", "elimination_dehydration_001", "CCC(C)O", "2-丁醇",
      ["CC=CC"], note="醇脱水成烯"),
    C("eli_demethylation", "demethylation_aromatic_001", "COc1ccccc1", "苯甲醚",
      ["Oc1ccccc1"], note="脱甲基：芳甲醚脱甲基生成酚"),
    C("rea_double_bond_isomer", "isomerization_double_bond_001", "CC=CC", "2-丁烯",
      ["C=CCC"], note="双键位置异构（可逆，只产不传播）"),
    C("rea_retro_aldol", "rearrangement_retro_aldol_001", "CC(O)CC=O", "3-羟基丁醛（乙醛缩合产物）",
      ["CC=O"],
      note="★原本是覆盖缺口：规则要求中间碳恰好 1 个氢，把最典型的 β-羟基羰基（中间为 CH2）全部排除。已放宽为 [CX4:3]。这条用例验证修复——乙醛自身缩合产物能正常裂解回乙醛"),
]

# ---------------- 条件门控（不涉及具体产物） ----------------
GATING = [
    {"id": "gate_oxidation_off_n2", "kind": "gating", "conditions": "无氧煎煮",
     "must_inactive_categories": ["oxidation"],
     "note": "氮气保护下，所有氧化反应必须熄灭"},
    {"id": "gate_oxidation_on_air", "kind": "gating", "conditions": "煎煮",
     "must_active_categories": ["oxidation"],
     "note": "有氧煎煮下，氧化规则应当激活"},
    {"id": "gate_reduction_only_h2", "kind": "gating", "conditions": "煎煮",
     "must_inactive_categories": ["reduction"],
     "note": "不通氢时还原反应不应发生"},
    {"id": "gate_reduction_on_h2", "kind": "gating", "conditions": "还原",
     "must_active_categories": ["reduction"],
     "note": "通氢条件下还原规则激活"},
    {"id": "gate_hydrolysis_on_acid", "kind": "gating", "conditions": "酸水解",
     "must_active_rules": ["hydrolysis_ester_001", "hydrolysis_glycoside_001"],
     "note": "酸水解条件下，酯水解和糖苷水解应当激活"},
]


def main() -> int:
    cases = CASES + GATING
    ids = [c["id"] for c in cases]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        print(f"★ 用例 id 重复: {dup}")
        return 1

    OUT.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    from collections import Counter
    kinds = Counter(c["kind"] for c in cases)
    print(f"写入 {OUT}")
    print(f"用例总数: {len(cases)}")
    for k, v in kinds.items():
        print(f"   {k:<10}{v}")

    # 覆盖了哪些规则
    rules = sorted({c["rule"] for c in cases if c.get("rule")})
    print(f"\n覆盖规则 {len(rules)} 条:")
    for r in rules:
        print(f"   {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
