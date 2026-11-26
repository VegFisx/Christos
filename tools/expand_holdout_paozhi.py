# -*- coding: utf-8 -*-
"""一次性：给 data/holdout_paozhi.json 追加 11 条 weak 案例（2026-11-22）。

原则：
  · 原有 6 条 strong 案例和 expected **一字不改**；
  · 新案例全部标 weak：它们在规则设计/证据文献里出现过，只能当回归集，
    不能算独立留出；
  · 结构与 iid 全部来自 tcm.db；无结构的产物用 kind=formula，不手写 SMILES；
  · expected 在运行之前写入并提交。
"""
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\data\holdout_paozhi.json")


def case(cid, herb_cn, herb_en, process_cn, process_en, cond, seed, target,
         rule, status, conf, reason, lit):
    return {
        "id": cid,
        "herb_cn": herb_cn, "herb_en": herb_en,
        "process_cn": process_cn, "process_en": process_en,
        "condition": cond,
        "holdout_strength": "weak",
        "seed": seed,
        "targets": [target],
        "bridge": "",
        "expected": {"status": status, "rule": rule, "confidence": conf,
                     "reason": reason},
        "literature_note": lit,
    }


NEW = [
    case("miyan_licorice_glycyrrhizin", "甘草", "Licorice", "蜜炙", "honey-frying",
         "炮制·蜜炙",
         {"iid": "HBIN028191", "name": "Glycyrrhizin", "formula": "C42H62O16"},
         {"label": "glycyrrhetinic acid", "kind": "key", "value": "HBIN002095",
          "formula": "C30H46O4", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "甘草酸（二葡萄糖醛酸苷）水解到甘草次酸；lit_cond 已实测命中同一规则",
         "DOI 10.1080/14786419.2026.2693245（蜜炙甘草成分变化）"),
    case("zhengzhi_ginseng_rb1_rg3", "人参", "Ginseng", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN027729", "name": "Ginsenoside rb1", "formula": "C54H92O23"},
         {"label": "ginsenoside rg3", "kind": "key", "value": "HBIN027751",
          "formula": "C42H72O13", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "Rb1 去糖得 Rg3；lit_cond 已实测命中",
         "DOI 10.3390/molecules25194390（不同炮制工艺的人参皂苷谱）"),
    case("zhengzhi_ginseng_rg1_rh1", "人参", "Ginseng", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN027746", "name": "Ginsenoside rg1", "formula": "C42H72O14"},
         {"label": "ginsenoside rh1", "kind": "key", "value": "HBIN027761",
          "formula": "C36H62O9", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "Rg1 去一个葡萄糖得 Rh1（C42H72O14 - C6H10O5）；与 Rb1 同族",
         "DOI 10.3390/molecules25194390（不同炮制工艺的人参皂苷谱）"),
    case("zhengzhi_ginseng_rg3_rg5", "人参", "Ginseng", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN027751", "name": "Ginsenoside rg3", "formula": "C42H72O13"},
         {"label": "ginsenoside rg5", "kind": "key", "value": "HBIN027756",
          "formula": "C42H70O12", "family": ["elimination_dehydration"]},
         "elimination_dehydration_001", "consistent", "medium",
         "Rg3 脱水得 Rg5（C42H72O13 - H2O）；若规则只给 Rk1 或不给脱水产物，则记为 miss",
         "DOI 10.3390/molecules25194390（不同炮制工艺的人参皂苷谱）"),
    case("zhengzhi_ginseng_rg3_rk1", "人参", "Ginseng", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN027751", "name": "Ginsenoside rg3", "formula": "C42H72O13"},
         {"label": "ginsenoside rk1", "kind": "key", "value": "HBIN027782",
          "formula": "C42H70O12", "family": ["elimination_dehydration"]},
         "elimination_dehydration_001", "consistent", "medium",
         "Rg3 脱水得 Rk1（与 Rg5 同分子式、双键位置不同）；规则若只给一种异构体，则记为 miss",
         "DOI 10.3390/molecules25194390（不同炮制工艺的人参皂苷谱）"),
    case("fuzi_aconitine_benzoylaconine", "附子", "Aconite", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN014582", "name": "Aconitine", "formula": "C34H47NO11"},
         {"label": "benzoylaconine", "kind": "key", "value": "HBIN017810",
          "formula": "C32H45NO10", "family": ["hydrolysis_ester"]},
         "hydrolysis_ester_001", "consistent", "high",
         "乌头碱 C8 乙酰酯水解得苯甲酰乌头原碱（C34H47NO11 - C2H2O）",
         "DOI 10.3389/fphar.2016.00367（双酯型生物碱酯水解）"),
    case("fuzi_mesaconitine_benzoylmesaconine", "附子", "Aconite", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN034775", "name": "Mesaconitine", "formula": "C33H45NO11"},
         {"label": "benzoylmesaconine", "kind": "key", "value": "HBIN017822",
          "formula": "C31H43NO10", "family": ["hydrolysis_ester"]},
         "hydrolysis_ester_001", "consistent", "high",
         "中乌头碱乙酰酯水解得苯甲酰中乌头原碱（C33H45NO11 - C2H2O）",
         "DOI 10.3389/fphar.2016.00367（双酯型生物碱酯水解）"),
    case("fuzi_hypaconitine_benzoylhypaconine", "附子", "Aconite", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN029816", "name": "Hypaconitine", "formula": "C33H45NO10"},
         {"label": "benzoylhypaconine", "kind": "key", "value": "HBIN017820",
          "formula": "C31H43NO9", "family": ["hydrolysis_ester"]},
         "hydrolysis_ester_001", "consistent", "high",
         "次乌头碱乙酰酯水解得苯甲酰次乌头原碱（C33H45NO10 - C2H2O）",
         "DOI 10.3389/fphar.2016.00367（双酯型生物碱酯水解）"),
    case("binglang_arecoline_guvacoline", "槟榔", "Areca seed", "炒焦", "char-frying",
         "炮制·炒焦",
         {"iid": "HBIN016699", "name": "Arecoline", "formula": "C8H13NO2"},
         {"label": "guvacoline", "kind": "key", "value": "HBIN028561",
          "formula": "C7H11NO2", "family": ["demethylation_n"]},
         "demethylation_n_001", "consistent", "high",
         "槟榔碱 N-脱甲基得去甲槟榔碱（guvacoline，C8H13NO2 - CH2）；lit_cond 已实测命中",
         "《美拉德反应对槟榔炮制过程中槟榔碱转化的影响》(2017)"),
    case("cangerzi_catr_atr", "苍耳子", "Xanthium fruit", "炒黄", "stir-frying",
         "炮制·炒黄",
         {"iid": "HBIN019719", "name": "Carboxyatractyloside", "formula": "C31H46O18S2"},
         {"label": "atractyloside skeleton", "kind": "formula",
          "value": "C30H46O16S2", "family": ["decarboxylation"]},
         "decarboxylation_001", "formula_only", "high",
         "CATR 加热脱羧得 ATR 骨架（C31H46O18S2 - CO2）；ATR 在 tcm.db 无结构，只能判分子式",
         "《苍耳子炮制前后羧基苍术苷和苍术苷的含量比较》(2013)"),
    case("heshouwu_thsg_aglycone", "何首乌", "Polygonum multiflorum", "蒸制", "steaming",
         "炮制·蒸制",
         {"iid": "HBIN003908", "name": "2,3,5,4'-tetrahydroxystilbene-2-O-beta-D-glucoside",
          "formula": "C20H22O9"},
         {"label": "THSG aglycone", "kind": "formula",
          "value": "C14H12O4", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "formula_only", "medium",
         "THSG 去葡萄糖得二苯乙烯苷元（C20H22O9 - C6H10O5 = C14H12O4）；苷元在 tcm.db 无结构，只能判分子式",
         "DOI 10.3389/fphar.2018.00934（何首乌炮制化学）"),
]


def main():
    d = json.loads(P.read_text(encoding="utf-8"))
    ids = {c["id"] for c in d["cases"]}
    added = 0
    for c in NEW:
        if c["id"] not in ids:
            d["cases"].append(c)
            added += 1
    d["expanded_at"] = "2026-11-22"
    d["tiers"] = {
        "strong": "从未用于设计规则的案例；只把这 6 例的分数当作独立留出",
        "weak": "规则设计/证据文献已覆盖的案例，只作回归集，不当作独立验证",
    }
    d["weak_cases_frozen_note"] = (
        "11 条 weak 案例及其 expected 在 2026-11-22 运行前写入并提交；"
        "strong 6 例的 expected 未改")
    d["protocol"].append(
        "5. 2026-11-22 扩例：只新增 weak 案例，strong 6 例与 expected 不变；先提交再跑。")
    P.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("原 %d 例，新增 %d，现 %d 例" % (len(ids), added, len(d["cases"])))


if __name__ == "__main__":
    main()
