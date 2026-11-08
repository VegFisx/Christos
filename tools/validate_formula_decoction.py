#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""方剂煎煮的文献对照：四逆汤（附子 + 甘草），煎煮 1 轮，看产物 + 路径 + 反应族。

口径与前三轮（文献回溯 / 炮制）一致：**产物一致 + 路径一致 + 反应族符合文献**。
文献依据（本轮只取这一类反应，不引孤证）：

  * 附子中双酯型二萜生物碱（乌头碱 / 中乌头碱 / 次乌头碱）在 100 °C 水相加热时，
    C8 位乙酰基水解，得到对应的**苯甲酰单酯型**生物碱（苯甲酰乌头原碱 / 苯甲酰中乌头原碱 /
    苯甲酰次乌头原碱）；继续水解得到的醇胺型（乌头原碱等）毒性更低。
    机制与温度条件见 <https://www.301as.com/2117.html> 与
    <https://www.brion.org.tw/_tw/research_content.php?id=317>（DDA → MDA 的水解路径）。
  * 四逆汤合煎过程中配伍会影响生物碱含量（单酯型/双酯型降低），
    见 <https://zgywjj.magtechjournal.com/CN/article/downloadArticleFile.do?attachType=PDF&id=3556>。

为什么种子只取「双酯型」：如果直接把苯甲酰单酯当种子，产物当然在场，等于自己证明自己。
所以种子只放底物侧，目标只放在产物侧。

用法：
    python -I tools\\validate_formula_decoction.py            # 跑全部案例
    python -I tools\\validate_formula_decoction.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import query_base as qb            # noqa: E402
import reaction_paths as rp        # noqa: E402
import validate_literature_conversions as V   # noqa: E402

import os

_DB_PATH = os.environ.get("CHEMCREACT_TCM_DB") or "D:/TCMAI/tcm.db"
DB = "file:%s?mode=ro" % _DB_PATH.replace("\\", "/")
OUT_JSON = ROOT / "reports" / "formula_decoction_20261104.json"

# ---------------------------------------------------------------- 方剂定义
# 四逆汤：附子（君）+ 干姜 + 甘草。本文件先验「乌头碱类水解」这条链，
# 干姜与甘草只作为共存底物放进同一锅（文献口径是合煎），不做单味归因。
FORMULA = {
    "name": "四逆汤",
    "herbs": {"附子": "HERB001776", "甘草": "HERB001779"},
    # 种子只取底物侧（双酯型），见文件头「为什么」。
    "seed_names": [
        "Aconitine", "Mesaconitine", "Hypaconitine",
        "Glycyrrhizin", "Liquiritin",
    ],
    # 目标只取产物侧（单酯型 / 醇胺型）
    "targets": [
        ("benzoylaconine", "HBIN017810", ("hydrolysis_ester",)),
        ("benzoylmesaconine", "HBIN017822", ("hydrolysis_ester",)),
        ("benzoylhypaconine", "HBIN017820", ("hydrolysis_ester",)),
    ],
}

# 第二步（桥接）：单酯型再水解成醇胺型，同样只放底物侧
BRIDGE = {
    "seed": ("Benzoylaconine", "HBIN017810"),
    "target": ("aconine", "HBIN014572", ("hydrolysis_ester",)),
}


def db():
    return sqlite3.connect(DB, uri=True)


def load_seeds(con, formula):
    """按名字挑种子（只读 tcm.db）。名字找不到就报错，不猜结构。"""
    names = [n.lower() for n in formula["seed_names"]]
    ids = {}
    for h, hid in formula["herbs"].items():
        rows = con.execute(
            "select c.name_en, c.ingredient_id, c.smiles, c.formula "
            "from herb_compound hc join compounds c on c.ingredient_id=hc.ingredient_id "
            "where hc.herb_id=? and c.smiles is not null and c.smiles<>''", (hid,)).fetchall()
        for nm, iid, smi, form in rows:
            if (nm or "").lower() in names and nm not in ids:
                ids[nm] = {"name": nm, "id": iid, "smiles": smi, "formula": form, "herb": h}
    missing = [n for n in formula["seed_names"] if n not in ids]
    return [ids[n] for n in formula["seed_names"] if n in ids], missing


def run_batch(seeds, cond_name, max_pairs=200, rounds=1, max_products_per_pair=64):
    """方剂合煎：多底物跑 rounds 轮（默认 1 轮）。"""
    t0 = time.time()
    spec = qb.RunSpec(
        seeds=[(s["name"], s["smiles"], s["herb"]) for s in seeds],
        cond_name=cond_name,
        rounds=rounds,
        max_pairs=max_pairs,
        max_products_per_pair=max_products_per_pair,
        use_curated_templates=True,
        strict_redox_gate=True,
    )
    inv = qb.build_inventory(spec, score=False, use_cache=False)
    hops = rp.expand_co_products(rp.hops_from_paths(inv.paths))
    return hops, round(time.time() - t0, 1)


def find_direct(con, hops, target_id, prefixes):
    """目标是否直接出现在产物侧；并检查给出它的那条跳的规则族。"""
    row = con.execute("select smiles, name_en from compounds where ingredient_id=?",
                      (target_id,)).fetchone()
    if not row:
        return {"status": "target_not_in_db"}
    tsmi, tname = row
    want = V.full_inchikey(tsmi)[:14].upper()
    hits = []
    for h in hops:
        try:
            if V.full_inchikey(h.product)[:14].upper() == want:
                hits.append(h)
        except Exception:
            continue
    if not hits:
        return {"status": "not_found", "target": tname, "target_id": target_id}

    def rules_of(h):
        out = [h.rule] if h.rule else []
        for x in (getattr(h, "alt_rules", "") or "").split(","):
            x = x.strip()
            if x and x not in out:
                out.append(x)
        return out

    def fam(rule):
        r = (rule or "").lower()
        return any(p.lower() in r for p in prefixes)

    # 同一结构可能由多条规则给出（去重时只留主规则名，其余在 alt_rules），
    # 所以「反应族对不对」要对全部规则取并集判断 —— 否则会把水解误判成酯交换。
    pick = next((h for h in hits if any(fam(x) for x in rules_of(h))), hits[0])
    fam_rule = next((x for x in rules_of(pick) if fam(x)), "")
    ok = bool(fam_rule)
    return {
        "status": "consistent" if ok else "product_only",
        "target": tname, "target_id": target_id,
        # rule 给出「符合文献反应族」的那条；primary_rule 是台账里先占到名字的那条
        "rule": fam_rule or pick.rule,
        "primary_rule": pick.rule,
        "rules_all": rules_of(pick),
        "from": pick.source_name or pick.source[:24],
        "chain": [fam_rule or pick.rule],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(OUT_JSON))
    ap.add_argument("--cond", default="煎煮")
    ap.add_argument("--max-pairs", type=int, default=200, dest="max_pairs")
    a = ap.parse_args()

    con = db()
    seeds, missing = load_seeds(con, FORMULA)
    print("方剂：%s（%s）" % (FORMULA["name"], " + ".join(FORMULA["herbs"])))
    print("条件：%s；种子 %d 个" % (a.cond, len(seeds)))
    for s in seeds:
        print("   %-16s %-12s %-8s %s" % (s["name"][:16], s["id"], s["formula"], s["herb"]))
    if missing:
        print("   ⚠ 库里没找到：%s" % "、".join(missing))

    hops, secs = run_batch(seeds, a.cond, a.max_pairs)
    print("第一轮：%d 跳，%.1f s" % (len(hops), secs))
    by_rule = {}
    for h in hops:
        by_rule[h.rule] = by_rule.get(h.rule, 0) + 1
    for k in sorted(by_rule, key=lambda x: -by_rule[x])[:8]:
        print("   %-34s %d" % (k, by_rule[k]))

    cases = []
    for label, tid, pref in FORMULA["targets"]:
        res = find_direct(con, hops, tid, pref)
        res["case"] = label
        res["step"] = "round1"
        cases.append(res)
        print("   [%s] %-14s %s" % (res.get("status"), label, res.get("rule", "")))

    # 桥接第二步：苯甲酰乌头原碱单独再跑一轮 → 乌头原碱
    bsmi, bname = BRIDGE["seed"][0], BRIDGE["seed"][0]
    brow = con.execute("select smiles from compounds where ingredient_id=?",
                       (BRIDGE["seed"][1],)).fetchone()
    if brow:
        bseeds = [{"name": "Benzoylaconine", "smiles": brow[0], "herb": "附子"}]
        bhops, bsecs = run_batch(bseeds, a.cond, 50)
        print("桥接：%s 单跑一轮 → %d 跳，%.1f s" % (bname, len(bhops), bsecs))
        res = find_direct(con, bhops, BRIDGE["target"][1], BRIDGE["target"][2])
        res["case"] = BRIDGE["target"][0]
        res["step"] = "bridge"
        cases.append(res)
        print("   [%s] %-14s %s" % (res.get("status"), BRIDGE["target"][0], res.get("rule", "")))

    ok = sum(1 for c in cases if c.get("status") == "consistent")
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "validation_type": "formula decoction literature comparison: product + path + rule family",
        "formula": FORMULA["name"],
        "herbs": FORMULA["herbs"],
        "seed_names": FORMULA["seed_names"],
        "missing_seeds": missing,
        "condition": a.cond,
        "max_pairs": a.max_pairs,
        "n_hops_round1": len(hops),
        "seconds_round1": secs,
        "rules_round1": by_rule,
        "summary": {"n_cases": len(cases), "n_consistent": ok},
        "cases": cases,
    }
    Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出：%s" % a.json)
    print("小结：%d/%d 条目标一致" % (ok, len(cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
