# -*- coding: utf-8 -*-
"""桂枝汤 / 麻黄汤：方剂煎煮验证 + 规则族覆盖统计。

口径与第三轮（四逆汤）、第九十三轮（黄芩汤）一致：
  - 种子只取底物侧（从 tcm.db 按名字取，不手写 SMILES）
  - 目标只取产物侧，按 InChIKey 前 14 位匹配
  - 三条同时满足才算 consistent：产物结构 + 路径连得上 + 反应族符合文献
  - 「新规则族」= 命中规则不在前几轮验证报告出现过的规则集合里

停止规则（写进报告）：连续 2 个方没有引入新规则族 → 判定反应类型饱和，停止逐方验证。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "core", _ROOT / "conditions", _ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import validate_formula_decoction as F   # noqa: E402  复用 db/load_seeds/run_batch/find_direct

OUT = _ROOT / "reports" / "formula_coverage_20261106.json"

FORMULAS = [
    {
        "name": "桂枝汤",
        "herbs": {"桂枝": "HERB002062", "白芍": "HERB000267", "甘草": "HERB001779",
                  "生姜": "HERB005017", "大枣": "HERB001164"},
        "seed_names": ["Cinnamaldehyde", "Paeoniflorin", "Glycyrrhizin",
                       "Liquiritin", "6-Gingerol"],
        "targets": [
            # 桂皮醛 → 桂皮酸：文献是氧化（醛→酸）
            ("cinnamic_acid", "HBIN020657", ("oxidation", "dehydrogen", "aldehyde")),
            # 甘草苷 → 甘草素：糖苷水解
            ("liquiritigenin", "HBIN006534", ("hydrolysis_glycoside",)),
            # 甘草酸 → 甘草次酸：糖苷水解
            ("glycyrrhetinic_acid", "HBIN028184", ("hydrolysis_glycoside",)),
            # 芍药苷 → 芍药苷元酮：煎煮受热降解（糖苷水解/脱水/消除）
            ("paeoniflorigenone", "HBIN038605", ("hydrolysis", "elimination", "dehydration")),
        ],
        "bridge": None,
    },
    {
        "name": "麻黄汤",
        "herbs": {"麻黄": "HERB003658", "桂枝": "HERB002062",
                  "苦杏仁": "HERB003174", "甘草": "HERB001779"},
        "seed_names": ["Ephedrine", "Cinnamaldehyde", "Amygdalin", "Glycyrrhizin"],
        "targets": [
            # 苦杏仁苷 → 野樱苷：一次脱葡萄糖
            ("prunasin", "HBIN040963", ("hydrolysis_glycoside",)),
            # 苦杏仁苷 → 苯甲醛（经野樱苷、扁桃腈两步），靠 bridge 才能到
            ("benzaldehyde", "HBIN017734", ("hydrolysis", "elimination", "cyanohydrin")),
        ],
        # 桥接：野樱苷再跑一轮 → 苯甲醛
        "bridge": {"seed": ("Prunasin", "HBIN040963"),
                   "targets": [("benzaldehyde", "HBIN017734",
                                ("hydrolysis", "elimination", "cyanohydrin"))]},
    },
    {
        # 专冲 elimination_dehydration / 醚环化：柴胡皂苷 → 柴胡皂苷元
        "name": "小柴胡汤",
        "herbs": {"柴胡": "HERB000638", "黄芩": "HERB002563", "半夏": "HERB000330",
                  "人参": "HERB004609", "甘草": "HERB001779"},
        "seed_names": ["Saikosaponin D", "Baicalin", "Wogonoside", "Glycyrrhizin"],
        "targets": [
            # 柴胡皂苷 a → 柴胡皂苷元 F（文献配对；d→D 是立体差异，2D 引擎不区分）
            ("saikogenin_f", "HBIN042778",
             ("hydrolysis_glycoside", "hydrolysis_acetal")),
            # 柴胡皂苷 d → 柴胡皂苷元 d：脱两个糖 + 醚环化/脱水
            ("saikogenin_d", "HBIN042776",
             ("hydrolysis", "elimination", "dehydration", "cyclization")),
            # 黄芩苷 → 黄芩素：糖苷水解（已知族，作对照）
            ("baicalein", "HBIN017508", ("hydrolysis_glycoside",)),
            # 汉黄芩苷 → 汉黄芩素：糖苷水解
            ("wogonin", "HBIN048372", ("hydrolysis_glycoside",)),
        ],
        "bridge": None,
    },
]


def load_seeds_ci(con, formula):
    """同 F.load_seeds，但键名全部小写比较。

    踩过的坑：库里写的是 `Saikosaponin d` / `6-gingerol`，配方表里写 `Saikosaponin D` /
    `6-Gingerol`，大小写不一致会被误判成「库里没有这个种子」——`F.load_seeds` 的匹配是
    小写的，但「缺哪些」的判定用的是原始大小写，于是漏报。
    """
    names = {n.lower() for n in formula["seed_names"]}
    want = {n.lower(): n for n in formula["seed_names"]}
    got = {}
    for h, hid in formula["herbs"].items():
        rows = con.execute(
            "select c.name_en, c.ingredient_id, c.smiles, c.formula "
            "from herb_compound hc join compounds c on c.ingredient_id=hc.ingredient_id "
            "where hc.herb_id=? and c.smiles is not null and c.smiles<>''", (hid,)).fetchall()
        for nm, iid, smi, form in rows:
            key = (nm or "").lower()
            if key in names and key not in got:
                got[key] = {"name": nm, "id": iid, "smiles": smi, "formula": form, "herb": h}
    missing = [want[k] for k in want if k not in got]
    ordered = [got[k] for k in want if k in got]
    return ordered, missing


def load_baseline_rules() -> set[str]:
    """前几轮验证报告里出现过的规则 id（用来判断「新族」）。"""
    out: set[str] = set()
    for name in ("literature_paths_20261104.json", "paozhi_paths_20261104.json",
                 "formula_decoction_20261104.json", "formula_followups_20261104.json"):
        p = _ROOT / "reports" / name
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("rule", "primary_rule", "rules_all", "rules_round1",
                             "expected_rules_matched", "hit_rules"):
                        if isinstance(v, str):
                            out.add(v.strip())
                        elif isinstance(v, list):
                            out.update(str(x).strip() for x in v)
                        elif isinstance(v, dict):
                            out.update(str(x).strip() for x in v.keys())
                    else:
                        walk(v)
            elif isinstance(o, list):
                for x in o:
                    walk(x)
        walk(d)
    return {x for x in out if x and not x.startswith("(")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pairs", type=int, default=120, dest="max_pairs")
    ap.add_argument("--cond", default="煎煮")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args()

    con = F.db()
    baseline = load_baseline_rules()
    print(f"基线规则集合：{len(baseline)} 条（来自前几轮报告）")

    report = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "protocol": "公式化两步验证 + 规则族覆盖统计", "max_pairs": a.max_pairs,
              "baseline_rule_count": len(baseline), "formulas": []}

    all_new: set[str] = set()
    for f in FORMULAS:
        seeds, missing = load_seeds_ci(con, f)
        print(f"\n== {f['name']} == 种子 {len(seeds)} 个（缺 {missing or '无'}）")
        hops, secs = F.run_batch(seeds, a.cond, max_pairs=a.max_pairs)
        fams = {}
        for h in hops:
            for r in [h.rule] + [x.strip() for x in (getattr(h, "alt_rules", "") or "").split(",")]:
                if r:
                    fams[r] = fams.get(r, 0) + 1
        print(f"   一轮 {len(hops)} 跳 / {secs}s；命中规则 {len(fams)} 条")

        entry = {"name": f["name"], "n_seeds": len(seeds), "missing_seeds": missing,
                 "n_hops": len(hops), "seconds": secs, "targets": [],
                 "rules_hit": dict(sorted(fams.items(), key=lambda kv: -kv[1]))}

        for label, tid, prefixes in f["targets"]:
            r = F.find_direct(con, hops, tid, prefixes)
            r["label"] = label
            entry["targets"].append(r)
            print(f"   - {label}: {r.get('status')} 规则={r.get('rule') or '-'}")

        if f.get("bridge"):
            bs, bm = f["bridge"]["seed"]
            row = con.execute("select ingredient_id, name_en, smiles from compounds "
                              "where lower(name_en)=lower(?)", (bs,)).fetchone()
            if row:
                bseed = [{"name": row[1], "id": row[0], "smiles": row[2], "herb": "bridge"}]
                bhops, bsecs = F.run_batch(bseed, a.cond, max_pairs=a.max_pairs)
                entry["bridge"] = {"seed": bs, "n_hops": len(bhops), "seconds": bsecs, "targets": []}
                print(f"   桥接 {bs}: {len(bhops)} 跳 / {bsecs}s")
                for label, tid, prefixes in f["bridge"]["targets"]:
                    r = F.find_direct(con, bhops, tid, prefixes)
                    r["label"] = label
                    entry["bridge"]["targets"].append(r)
                    entry["targets"].append({**r, "label": label + "(桥接)"})
                    print(f"   - {label}(桥接): {r.get('status')} 规则={r.get('rule') or '-'}")
            else:
                entry["bridge"] = {"seed": bs, "error": "seed_not_in_db"}
                print(f"   桥接种子 {bs} 不在库里")

        new = sorted(set(fams) - baseline)
        entry["new_rules"] = new
        all_new.update(new)
        print(f"   新规则族：{new or '无'}")
        report["formulas"].append(entry)

    report["all_new_rules"] = sorted(all_new)
    report["saturated"] = len(all_new) == 0
    Path(a.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n新规则族合计 {len(all_new)} 条；写出 {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
