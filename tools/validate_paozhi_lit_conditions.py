# -*- coding: utf-8 -*-
"""第 112 轮：用「文献记载的炮制条件」重跑，和「预设档」对比产物命中。

设计
----
每个案例跑两遍，除了条件之外完全一致（同一种子、同一轮数、同一套炮制证据规则）：

* preset 臂：用 conditions/templates.py 里的固定档（炒黄 165°C/10min 等）
* lit 臂   ：用文献报道的实际条件（温度/时长/pH/辅料），即 `--cond 炮制·自定义`
             + `--temperature/--time-min/--ph/--paozhi-adjuvant-kind`

判定沿用前三轮口径：目标产物**结构命中**（InChIKey 前 14 位）优先，
库里没有该结构时退回**分子式命中**。两个臂都记录产物数与命中规则。

用法
----
    python -I tools/validate_paozhi_lit_conditions.py [--out reports/paozhi_lit_cond_20261106.json]

注意
----
* 种子与目标结构全部来自 tcm.db **只读**（不手写 SMILES）
* 辅料共底物结构来自 rules/paozhi_adjuvants.json（同样来自 tcm.db 快照）
* 本脚本必须带 `if __name__ == "__main__":` 守卫：build_inventory 用 spawn 池
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "conditions", ROOT / "tools", ROOT / "sources"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import os

_DB_PATH = os.environ.get("CHEMCREACT_TCM_DB") or "D:/TCMAI/tcm.db"
DB = "file:%s?mode=ro" % _DB_PATH.replace("\\", "/")

# 预设档（preset 臂）与文献条件（lit 臂）逐条对照。
# literature 字段里的数值必须能在 reports/paper/paozhi_sources_20261031.json、
# conditions/verification 或者 rules/paozhi_evidence.json 的引句里找到出处，
# 否则不许写进来（AGENTS §十二）。
CASES: List[Dict] = [
    {
        "tag": "miyan_licorice",
        "label": "蜜炙甘草：甘草酸 → 甘草次酸",
        "seed": "HBIN028191",
        "target": ("key", "HBIN028184"),
        "preset": {"cond": "炮制·蜜炙", "adjuvant": "honey"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "honey",
                "cond_override": {"solvent": "none", "temperature": 120,
                                  "time_min": 13.5, "pH": 7.0, "atmosphere": "air"}},
        "lit_desc": "120 °C / 13.5 min（蜜炙甘草研究）",
        "source": "10.1080/14786419.2026.2693245",
    },
    {
        "tag": "cuyan_langdu",
        "label": "醋炙狼毒：JNB → 开环酸",
        "seed": "HBIN031562",
        "target": ("formula", "C20H28O5"),
        "preset": {"cond": "炮制·醋炙", "adjuvant": "auto"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "vinegar",
                "cond_override": {"solvent": "water", "temperature": 160,
                                  "time_min": 40, "pH": 1.6, "atmosphere": "air"}},
        "lit_desc": "160 °C / 6% 乙酸 / 40 min",
        "source": "10.19540/j.cnki.cjcmm.20221111.301",
    },
    {
        "tag": "chaohuang_cangerzi",
        "label": "炒黄苍耳子：CATR → ATR",
        "seed": "HBIN019719",
        "target": ("formula", "C30H46O16S2"),
        "preset": {"cond": "炮制·炒黄", "adjuvant": "none"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "none",
                "cond_override": {"solvent": "none", "temperature": 165,
                                  "time_min": 10, "pH": 7.0, "atmosphere": "air"}},
        "lit_desc": "160–170 °C（微炒，二手来源）；时长取档内 10 min",
        "source": "二手来源（见 template_verification 炒黄条目）",
    },
    {
        "tag": "zhengzhi_ginseng",
        "label": "蒸制人参：Rb1 → Rg3",
        "seed": "HBIN027729",
        "target": ("key", "HBIN003457"),
        "preset": {"cond": "炮制·蒸制", "adjuvant": "none"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "none",
                "cond_override": {"solvent": "water", "temperature": 98,
                                  "time_min": 150, "pH": 7.0, "atmosphere": "air"}},
        "lit_desc": "95–100 °C / 2–3 h（红参蒸制）",
        "source": "10.3390/molecules25194390 / 10.1016/j.jgr.2017.02.003",
    },
    {
        "tag": "chaijiao_binglang",
        "label": "炒焦槟榔：槟榔碱 → 去甲槟榔碱",
        "seed": "HBIN016699",
        "target": ("key", "HBIN028561"),
        "preset": {"cond": "炮制·炒焦", "adjuvant": "none"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "none",
                "cond_override": {"solvent": "none", "temperature": 200,
                                  "time_min": 20, "pH": 7.0, "atmosphere": "air"}},
        "lit_desc": "200 °C / 20 min（焦槟榔代表值；区间见 217–286 °C 的焦麦芽报道）",
        "source": "10.7501/j.issn.0253-2670.2026.06.008（区间来源）",
    },
    {
        "tag": "zhengzhi_Heshouwu",
        "label": "蒸制何首乌：THSG → 苷元",
        "seed": "HBIN003908",
        "target": ("formula", "C14H12O4"),
        "preset": {"cond": "炮制·蒸制", "adjuvant": "none"},
        "lit": {"cond": "炮制·自定义", "adjuvant": "none",
                "cond_override": {"solvent": "water", "temperature": 98,
                                  "time_min": 150, "pH": 7.0, "atmosphere": "air"}},
        "lit_desc": "95–100 °C / 2–3 h（与红参蒸制同源的蒸制工况）",
        "source": "10.3390/molecules25194390（工况借用，非何首乌原文）",
    },
]


def db_row(iid: str) -> Optional[Dict]:
    con = sqlite3.connect(DB, uri=True)
    try:
        cur = con.execute(
            "SELECT ingredient_id,name_en,formula,smiles,inchi_key "
            "FROM compounds WHERE ingredient_id=?", (iid,))
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r[0], "name": r[1], "formula": r[2],
                "smiles": r[3], "ik": r[4] or ""}
    finally:
        con.close()


def adjuvant_seeds(kind: str, method: str) -> List[Dict]:
    import paozhi_adjuvants as PA
    _MAP = {"honey": "蜜炙", "wine": "酒炙", "vinegar": "醋炙",
            "salt": "盐炙", "ginger": "姜炙"}
    if kind in ("none", "", None):
        return []
    m = _MAP.get(kind, method)
    return [c for c in PA.describe(m) if c.get("smiles")]


def run_arm(case: Dict, arm: str) -> Dict:
    import templates as T
    import query_base as qb
    import validate_literature_paths as V

    spec = case[arm]
    cond_name = spec["cond"]
    cond = T.get_template(cond_name)
    over = dict(spec.get("cond_override") or {})
    seed = db_row(case["seed"])
    if not seed:
        return {"error": "seed_not_in_db"}
    seeds = [(seed["name"], seed["smiles"], "单味药")]
    for a in adjuvant_seeds(spec.get("adjuvant", "none"), cond_name.split("·")[-1]):
        seeds.append((a.get("name") or a.get("name_en") or "辅料",
                      a["smiles"], "辅料:%s" % (a.get("adjuvant") or "")))
    ids = V._paozhi_ids()
    rs = qb.RunSpec(seeds=seeds, cond_name=cond_name, rounds=1,
                    max_pairs=400, max_products_per_pair=64,
                    use_curated_templates=True, curated_rule_ids=ids,
                    use_base_templates=False, strict_redox_gate=True,
                    cond_override=over)
    t0 = time.time()
    inv = qb.build_inventory(rs)
    import reaction_paths as rp
    hops = rp.expand_co_products(rp.hops_from_paths(inv.paths))
    secs = round(time.time() - t0, 1)

    kind, value = case["target"]
    hit = None
    rules = []
    if kind == "key":
        tgt = db_row(value)
        want = (tgt or {}).get("ik", "")[:14]
        for h in hops:
            hk = ""
            try:
                from rdkit import Chem
                m = Chem.MolFromSmiles(h.product)
                if m is not None:
                    hk = Chem.MolToInchiKey(m)
            except Exception:
                hk = ""
            if want and hk[:14] == want:
                hit = {"product": h.product, "formula": h.product_formula,
                       "rule": h.rule, "match": "inchikey14"}
                rules.append(h.rule)
                break
        target_name = (tgt or {}).get("name", value)
    else:
        want = value
        for h in hops:
            if (h.product_formula or "") == want:
                hit = {"product": h.product, "formula": h.product_formula,
                       "rule": h.rule, "match": "formula"}
                rules.append(h.rule)
                break
        target_name = value

    return {
        "cond": cond_name,
        "cond_values": {"solvent": over.get("solvent", cond.solvent),
                        "temperature": over.get("temperature", cond.temperature),
                        "time_min": over.get("time_min", cond.time_min),
                        "pH": over.get("pH", cond.pH),
                        "atmosphere": over.get("atmosphere", cond.atmosphere)},
        "adjuvant": spec.get("adjuvant"),
        "n_products": len({h.product for h in hops}),
        "n_hops": len(hops),
        "seconds": secs,
        "hit": hit,
        "target_name": target_name,
        "all_rules_seen": sorted({h.rule for h in hops}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/paozhi_lit_cond_20261106.json")
    args = ap.parse_args()

    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "protocol": {"rounds": 1, "max_pairs": 400,
                        "curated_rule_ids": "rules/paozhi_evidence.json",
                        "use_base_templates": False,
                        "criterion": "结构(InChIKey14) 优先，其次分子式"},
           "cases": []}
    improved = same = worse = 0
    for c in CASES:
        rec = {"tag": c["tag"], "label": c["label"],
               "source": c["source"], "lit_desc": c["lit_desc"]}
        for arm in ("preset", "lit"):
            try:
                rec[arm] = run_arm(c, arm)
            except Exception as ex:      # noqa: BLE001 —— 打印，不静默
                rec[arm] = {"error": "%s: %s" % (type(ex).__name__, ex)}
        p = (rec.get("preset") or {}).get("hit")
        l = (rec.get("lit") or {}).get("hit")
        rec["verdict"] = ("lit_only" if (l and not p) else
                          "preset_only" if (p and not l) else
                          "both" if (p and l) else "neither")
        if rec["verdict"] == "lit_only":
            improved += 1
        elif rec["verdict"] == "preset_only":
            worse += 1
        else:
            same += 1
        out["cases"].append(rec)
        print("== %-20s %s" % (rec["tag"], rec["label"]))
        for arm in ("preset", "lit"):
            a = rec.get(arm) or {}
            if a.get("error"):
                print("   %-6s ERROR %s" % (arm, a["error"]))
                continue
            v = a["cond_values"]
            print("   %-6s %-12s %s°C/%smin/pH%s/%s  adj=%-7s 产物 %-4d 命中 %s"
                  % (arm, a["cond"], v["temperature"], v["time_min"], v["pH"],
                     v["atmosphere"], a.get("adjuvant"), a["n_products"],
                     (a["hit"] or {}).get("rule") or "—"))
        print("   → %s" % rec["verdict"])

    out["summary"] = {"n_cases": len(CASES), "lit_only": improved,
                      "preset_only": worse, "same": same}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print("\n汇总：文献条件多命中 %d 条 / 预设档多命中 %d 条 / 打平或都没中 %d 条"
          % (improved, worse, same))
    print("写出 %s" % args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
