# -*- coding: utf-8 -*-
r"""第二批反应级用例：补上未覆盖的 21 条启用规则。

★ 原则：每条用例先写【化学上正确的产物】，再让引擎跑。
  不一致的地方才有价值——那才是要找的 bug。
  （上一轮就是这么抓到 Michael 区域选择性和糖苷水解的）

  双反应物规则的第二反应物由 co_substrate_pool 提供，用例里写池子里实际会用的那个。
"""

from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
OUT = HERE / "reaction_cases2.json"


def C(cid, rule, smiles, name, expect_any=None, note="", conditions="煎煮"):
    return {
        "id": cid, "kind": "rule", "rule": rule, "smiles": smiles, "name": name,
        "conditions": conditions, "expect_any": expect_any or [], "forbid": [],
        "note": note,
    }


CASES = [
    # ---- 水解 / 水合 ----
    C("hyd_phosphate", "hydrolysis_phosphate_001", "COP(=O)(O)O", "磷酸单甲酯",
      ["CO"], note="磷酸酯水解，放出甲醇"),
    C("hyd_hemiacetal", "hydrolysis_hemiacetal_001", "COC(C)O", "甲氧基乙醇(半缩醛)",
      ["CC=O"], note="半缩醛水解回到醛 + 醇"),
    C("hyd_epoxide", "hydrolysis_epoxide_001", "CC1CO1", "环氧丙烷",
      ["CC(O)CO"], note="环氧化物开环成邻二醇"),
    C("hyd_imine", "hydrolysis_imine_001", "CN=Cc1ccccc1", "N-甲基苯甲亚胺",
      ["O=Cc1ccccc1"], note="亚胺水解回到醛 + 胺"),

    # ---- 水合 ----
    C("hyd_alkene", "hydration_alkene_001", "CC=C", "丙烯",
      ["CC(C)O", "CCCO"], note="烯烃水合生成醇（马氏/反马氏两种都可能）"),
    C("hyd_enone", "hydration_enone_001", "C=CC=O", "丙烯醛",
      ["OCCC=O"], note="α,β-不饱和羰基水合生成 β-羟基醛"),

    # ---- 氧化 ----
    C("ox_amine", "oxidation_amine_001", "CCN", "乙胺",
      ["CC=N", "CC=O"], note="胺氧化生成亚胺（进一步可水解成羰基）"),
    C("ox_epoxide", "oxidation_epoxide_001", "CC=C", "丙烯",
      ["CC1CO1"], note="双键环氧化生成环氧化物"),
    C("ox_dehydro_enone", "oxidation_dehydrogenation_enone_001", "CCCC=O", "丁醛",
      ["CC=CC=O"], note="脱氢生成 α,β-不饱和羰基"),
    C("ox_sulfoxide_sulfone", "oxidation_sulfoxide_to_sulfone_001", "CS(C)=O", "DMSO",
      ["CS(C)(=O)=O"], note="亚砜进一步氧化成砜"),

    # ---- 还原 ----
    C("red_quinone", "reduction_quinone_001", "O=C1C=CC=CC1=O", "邻苯醌",
      ["Oc1ccccc1O"],
      note="醌还原成邻苯二酚。★规则的 [O]=[C][C]=[O] 要求两个羰基【相邻】，对苯醌（1,4-）不匹配", conditions="还原"),

    # ---- 消除 ----
    C("eli_deamination", "elimination_deamination_001", "NCCc1ccccc1", "2-苯乙胺",
      ["O=CCc1ccccc1"], note="氧化脱氨生成醛"),
    C("eli_amide_to_nitrile", "elimination_amide_to_nitrile_001", "CC(N)=O", "乙酰胺",
      ["CC#N"], note="酰胺高温脱水成腈"),

    # ---- 重排 ----
    C("rea_keto_enol", "tautomerization_keto_enol_001", "CC(C)=O", "丙酮",
      ["CC(O)=C"], note="酮-烯醇互变异构", conditions="室温浸泡"),

    # ---- 酯化 ----
    C("est_delta_lactone", "esterification_delta_lactone_001", "OCCCCC(=O)O", "5-羟基戊酸",
      ["O=C1CCCCO1"], note="δ-羟基酸分子内酯化生成六元内酯"),

    # ---- 缩合 ----
    C("cond_maillard", "maillard_simplified_001", "OCC=O", "羟乙醛",
      ["O=CC=O"], note="美拉德简化：α-羟基醛氧化成 α-二羰基"),

    # ---- 双反应物（第二反应物来自 co_substrate_pool）----
    C("bi_glycosylation", "condensation_glycosylation_001",
      "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O", "葡萄糖(端基羟基)",
      ["CCO[C@H]1O[C@@H](CO)[C@H](O)[C@@H](O)[C@@H]1O",
       "CCO[C@@H]1O[C@H](CO)[C@@H](O)[C@H](O)[C@H]1O"],
      note="糖苷化：葡萄糖端基羟基与醇池里的乙醇成苷。★成苷时端基构型可以翻转（端基异构化），所以 α/β 两种都算对", conditions="醇提"),
    C("bi_hemiacetal", "condensation_hemiacetal_001", "O=Cc1ccccc1", "苯甲醛",
      ["OC(OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O)c1ccccc1", "COC(O)c1ccccc1"],
      note="半缩醛形成：苯甲醛 + 醇池里的醇。★实测引擎取的是池子里的葡萄糖（分子最大），不是甲醇", conditions="室温浸泡"),
    C("bi_michael_amine", "addition_michael_amine_001", "C=CC=O", "丙烯醛",
      ["O=CCCNCC(=O)O"],
      note="★Michael 加成(胺)：氮必须加在 β碳上 → 3-氨基丙醛的衍生物。"
           "与硫醇版同源，上一轮一起修过。"
           "★原期望是 3-甲氨基丙醛(CNCCC=O)，那是照【甲胺】算的；"
           "甲胺在煎煮水里不存在，已从池子里移除（tools/audit_cosubstrates.py），"
           "现按药材真实存在的【甘氨酸】出产物", conditions="室温浸泡"),
    C("bi_aldol", "condensation_aldol_001", "CC=O", "乙醛",
      ["CC(O)CC=O"],
      note="醇醛缩合：乙醛 + 醛池里的乙醛 → 3-羟基丁醛", conditions="室温浸泡"),
    C("bi_thiohemiacetal", "addition_thiohemiacetal_001", "O=Cc1ccccc1", "苯甲醛",
      ["CSC(O)c1ccccc1"],
      note="硫代半缩醛：苯甲醛 + 硫醇池里的甲硫醇", conditions="室温浸泡"),

    # ---- 对位醌/酚（第 25 轮补「论文承诺却没实现」的蒽醌那一类时加的规则）----
    # 这两条规则加了之后一直【没有验收用例】，只是当时用临时脚本验过。
    # 底物一律用【无歧义】的小分子 —— 手写复杂天然产物 SMILES 已经错过两次。
    C("ox_para_diphenol", "oxidation_diphenol_para_001", "Oc1ccc(O)cc1", "对苯二酚",
      ["O=C1C=CC(=O)C=C1"],
      note="★对位★二酚氧化成醌：对苯二酚 -2H +O → 对苯醌 (C6H6O2 → C6H4O2)",
      conditions="氧化"),
    C("ox_para_anthrahydroquinone", "oxidation_diphenol_para_001",
      "Oc1c2ccccc2c(O)c2ccccc12", "9,10-蒽氢醌",
      ["O=C1c2ccccc2C(=O)c2ccccc21"],
      note="★这就是加这条规则的原因★ 论文说明写着「丹参酮、大黄蒽醌」，"
           "但原 SMARTS 只认两个羰基直接相连的邻位，蒽醌（相距 3 键）一直匹配不上。"
           "对苯二酚→对苯醌、蒽氢醌→蒽醌 都要能跑",
      conditions="氧化"),
    C("red_para_quinone", "reduction_quinone_para_001", "O=C1C=CC(=O)C=C1", "对苯醌",
      ["Oc1ccc(O)cc1"],
      note="对位醌还原成二酚：对苯醌 +H2 → 对苯二酚 (C6H4O2 → C6H6O2)",
      conditions="还原"),
    C("red_para_anthraquinone", "reduction_quinone_para_001",
      "O=C1c2ccccc2C(=O)c2ccccc21", "9,10-蒽醌",
      ["Oc1c2ccccc2c(O)c2ccccc12"],
      note="9,10-蒽醌 +H2 → 9,10-蒽氢醌 (C14H8O2 → C14H10O2)。"
           "论文说明承诺的「大黄蒽醌」就是这一类",
      conditions="还原"),
]


def main() -> int:
    ids = [c["id"] for c in CASES]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        print(f"★ id 重复: {dup}")
        return 1
    OUT.write_text(json.dumps(CASES, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(f"写入 {OUT}")
    print(f"用例数 {len(CASES)}")
    for c in CASES:
        print(f"   {c['id']:<26}{c['rule']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
