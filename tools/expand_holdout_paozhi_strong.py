# -*- coding: utf-8 -*-
"""一次性：给 data/holdout_paozhi.json 追加 5 条 strong 案例（2026-11-22）。

来源：本轮联网检索到、且规则设计时未用过的新药材/新转化。
结构/iid 全部来自 tcm.db；expected 在运行前写入并提交。
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
        "holdout_strength": "strong",
        "seed": seed,
        "targets": [target],
        "bridge": "",
        "expected": {"status": status, "rule": rule, "confidence": conf,
                     "reason": reason},
        "literature_note": lit,
    }


NEW = [
    case("zhiqiao_hesperidin_hesperetin", "枳壳", "Fructus Aurantii",
         "麸炒", "bran stir-frying", "炮制·炒黄",
         {"iid": "HBIN029196", "name": "Hesperidin", "formula": "C28H34O15"},
         {"label": "hesperetin", "kind": "key", "value": "HBIN029190",
          "formula": "C16H14O6", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "橙皮苷（芦丁糖苷）水解得橙皮素；麸炒后橙皮苷 6.34→4.23 μg/mL、"
         "橙皮素 0.50→0.93 μg/mL（文献定量）。条件档用炒黄近似麸炒。",
         "DOI 10.1016/j.fochx.2026.104646（Bran stir-frying remodels Fructus "
         "Aurantii through flavonoid deglycosylation and limonoid reduction）"),
    case("zhiqiao_naringin_naringenin", "枳壳", "Fructus Aurantii",
         "麸炒", "bran stir-frying", "炮制·炒黄",
         {"iid": "HBIN036380", "name": "Naringin", "formula": "C27H32O14"},
         {"label": "naringenin", "kind": "key", "value": "HBIN006816",
          "formula": "C15H12O5", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "柚皮苷水解得柚皮素；麸炒后柚皮苷 4.55→3.41 μg/mL、"
         "柚皮素 1.46→2.59 μg/mL（文献定量）。条件档用炒黄近似麸炒。",
         "DOI 10.1016/j.fochx.2026.104646（同上）"),
    case("huangqin_baicalin_baicalein", "黄芩", "Scutellaria baicalensis",
         "酒炙", "wine-frying", "炮制·酒炙",
         {"iid": "HBIN017516", "name": "Baicalin", "formula": "C21H18O11"},
         {"label": "baicalein", "kind": "key", "value": "HBIN017508",
          "formula": "C15H10O5", "family": ["hydrolysis_glycoside"]},
         "hydrolysis_glycoside_001", "consistent", "high",
         "黄芩苷（葡萄糖醛酸苷）水解得黄芩素；酒炙后黄芩苷/汉黄芩苷下降、"
         "黄芩素/汉黄芩素上升（文献多成分定量）。",
         "DOI 10.7501/j.issn.0253-2670.2020.09.019（黄芩酒炙前后化学成分变化）"),
    case("nvzhenzi_ligustroside_hydroxytyrosol", "女贞子", "Ligustri Lucidi Fructus",
         "酒蒸", "wine-steaming", "炮制·酒炙",
         {"iid": "HBIN033207", "name": "Ligustroside", "formula": "C25H32O12"},
         {"label": "hydroxytyrosol", "kind": "key", "value": "HBIN007117",
          "formula": "C8H10O3", "family": ["hydrolysis_glycoside"]},
         "", "miss", "medium",
         "文献报道酒蒸使女贞子苷（ligustroside）水解为羟基酪醇。现有糖苷规则只脱"
         "葡萄糖到苷元；羟基酪醇还需断裂裂环烯醚萜酯，预计 miss。"
         "条件档用酒炙近似酒蒸。",
         "DOI 10.1016/j.chroma.2020.461228（wine steaming of Ligustri Lucidi Fructus）"),
    case("huangqi_acetylastragaloside_astragaloside_iv", "黄芪", "Astragali Radix",
         "蜜炙", "honey-frying", "炮制·蜜炙",
         {"iid": "HBIN014450", "name": "Acetylastragaloside I", "formula": "C47H74O17"},
         {"label": "astragaloside IV", "kind": "key", "value": "HBIN017230",
          "formula": "C41H68O14", "family": ["hydrolysis_ester"]},
         "", "miss", "medium",
         "文献报道加热使乙酰黄芪苷脱乙酰生成黄芪甲苷 IV。单轮酯水解只脱一个乙酰，"
         "预计到不了黄芪甲苷 IV。",
         "DOI 10.3390/molecules27020575（Astragali radix processing methods）"),
]


def main():
    d = json.loads(P.read_text(encoding="utf-8"))
    ids = {c["id"] for c in d["cases"]}
    added = 0
    for c in NEW:
        if c["id"] not in ids:
            d["cases"].append(c)
            added += 1
    d["strong_expanded_at"] = "2026-11-22"
    d["strong_expansion_note"] = (
        "5 条 strong 新案例（枳壳2、黄芩、女贞子、黄芪）来自 2026-11-22 联网检索；"
        "规则设计时未使用；expected 在运行前写入并提交。")
    d["protocol"].append(
        "6. 2026-11-22 strong 扩例：5 条新药材案例，expected 先提交再跑；"
        "不得为它们补规则。")
    P.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("原 %d 例，新增 %d，现 %d 例" % (len(ids), added, len(d["cases"])))


if __name__ == "__main__":
    main()
