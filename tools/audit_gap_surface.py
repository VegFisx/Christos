# -*- coding: utf-8 -*-
"""缺口面审计：把「可能出缺口的地方」一次扫完。

四张表：
  1. holdout 矩阵：30 例在 evidence/production、r1/r3 下的状态与分类；
  2. 规则 × 反应型探针：11 条证据规则的 SMARTS 对代表性底物的匹配情况；
  3. 条件 × 规则激活：10 个炮制条件档下每条证据规则是否被激活；
  4. coverage 探针：代表性缺口反应型在 production 下能否被 coverage 补出产物。

只读规则/数据；不改 rules、不改引擎。输出：
  reports/gap_surface_audit_20261122.json

用法：
  python tools\\audit_gap_surface.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for _p in (ROOT / "core", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

import query_base as qb
from validate_literature_paths import run_once, _paozhi_ids

DB = "file:D:/TCMAI/tcm.db?mode=ro"
OUT = ROOT / "reports" / "gap_surface_audit_20261122.json"

CONDITIONS = [
    "炮制·炒黄", "炮制·炒焦", "炮制·炒炭", "炮制·蜜炙", "炮制·酒炙",
    "炮制·醋炙", "炮制·盐炙", "炮制·姜炙", "炮制·蒸制", "炮制·自定义",
]


def db():
    return sqlite3.connect(DB, uri=True).cursor()


def db_row(cur, iid):
    return cur.execute(
        "SELECT ingredient_id,name_en,formula,COALESCE(isomeric_smiles,smiles),inchi_key "
        "FROM compounds WHERE ingredient_id=?", (iid,)).fetchone()


def canon(smiles):
    try:
        m = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(m) if m else ""
    except Exception:
        return ""


# ---------------------------------------------------------------- 1 holdout
def holdout_matrix():
    hold = json.loads((ROOT / "data" / "holdout_paozhi.json").read_text(encoding="utf-8"))
    files = {
        "evidence_r1": "holdout_paozhi_20261122.json",
        "production_r1": "holdout_paozhi_20261122_production_r1.json",
        "evidence_r3": "holdout_paozhi_20261122_multiround_evidence_r3.json",
        "production_r3": "holdout_paozhi_20261122_multiround_production_r3.json",
    }
    by = {}
    for key, fn in files.items():
        p = ROOT / "reports" / fn
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        by[key] = {r.get("tag") or r.get("id"): r for r in d.get("cases", [])}

    rows = []
    for c in hold.get("cases", []):
        cid = c["id"]
        rec = {
            "id": cid,
            "tier": c.get("holdout_strength"),
            "condition": c.get("condition"),
            "expected": c.get("expected", {}).get("status"),
            "expected_rule": c.get("expected", {}).get("rule"),
            "seed": c.get("seed", {}).get("name"),
            "targets": [t.get("label") for t in c.get("targets", [])],
            "status": {}, "rules": {},
        }
        for key in files:
            r = (by.get(key) or {}).get(cid)
            if not r:
                continue
            rec["status"][key] = r.get("actual_status")
            rec["rules"][key] = [
                (t.get("rule") or "") for t in (r.get("targets") or [])
                if t.get("status") not in ("miss", "pending_round2", None)
            ]
        s1 = rec["status"].get("evidence_r1")
        s3 = rec["status"].get("evidence_r3")
        p1 = rec["status"].get("production_r1")
        p3 = rec["status"].get("production_r3")
        if s1 == "consistent":
            rec["class"] = "curated_hit"
        elif p1 == "product_only" or p3 == "product_only":
            rec["class"] = "coverage_product_only"
        elif s1 == "miss" and s3 == "consistent":
            rec["class"] = "multi_step_hit"
        elif s1 == "miss" and (p1 == "consistent" or p3 == "consistent"):
            rec["class"] = "coverage_path"
        elif "formula_only" in (s1, p1, s3, p3):
            rec["class"] = "formula_level"
        else:
            rec["class"] = "rule_gap"
        rows.append(rec)
    return rows


# ---------------------------------------------------------------- 2 rules × probes
RULE_PROBES = [
    ("benzylic_oxidation", "OCc1ccccc1", "benzyl alcohol -> aldehyde"),
    ("aromatic_o_demethylation", "COc1ccccc1", "anisole -> phenol"),
    ("cyclic_ether_5ring", "C1CCOC1", "THF ring opening"),
    ("epoxide_3ring", "C1CO1", "ethylene oxide opening"),
    ("acyclic_ether", "CCOCC", "diethyl ether cleavage"),
    ("glycoside_hydrolysis", "OC[C@H]1O[C@@H](Oc2ccccc2)[C@H](O)[C@@H](O)[C@@H]1O", "phenyl glucoside"),
    ("ester_hydrolysis", "CC(=O)OCC", "ethyl acetate"),
    ("esterification", "CC(=O)O.CCO", "acetic acid + ethanol"),
    ("lactone_5ring", "O=C1CCCO1", "gamma-butyrolactone"),
    ("n_methyl_amine", "CN(C)Cc1ccccc1", "N,N-dimethylbenzylamine"),
    ("secondary_alcohol_dehydration", "CC(C)O", "isopropanol"),
    ("alpha_hydroxy_aldehyde", "O=CCO", "glycolaldehyde"),
    ("allylic_alcohol", "OCC=C", "allyl alcohol"),
    ("decarboxylation", "O=C(O)CC(=O)O", "malonic acid"),
    ("sugar_dehydration", "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O", "glucose"),
    ("sulfite_esterification", "HBIN038606", "paeoniflorin"),
    ("alkaloid_rearrangement", "HBIN045003", "strychnine"),
    ("oxidative_aromatization", "HBIN026264", "evodiamine"),
]


def rule_probe_matrix():
    rules = json.loads((ROOT / "rules" / "rules.json").read_text(encoding="utf-8"))
    rules = rules.get("rules") if isinstance(rules, dict) else rules
    ids = set(_paozhi_ids())
    smarts = {r["id"]: r.get("smarts", "") for r in rules
              if isinstance(r, dict) and r.get("id") in ids}
    cur = db()
    out = []
    for typ, smi, note in RULE_PROBES:
        if str(smi).startswith("HBIN"):
            row = db_row(cur, smi)
            if not row:
                out.append({"type": typ, "probe": note, "error": "missing %s" % smi,
                            "matched_rules": [], "covered": False})
                continue
            smi, note = row[3], row[1]
        m = Chem.MolFromSmiles(smi)
        matched = []
        if m is not None:
            for rid, sm in smarts.items():
                if not sm:
                    continue
                # 规则里是反应 SMARTS；只取左侧做底物匹配。
                left = sm.split(">>", 1)[0].strip()
                try:
                    pat = Chem.MolFromSmarts(left)
                    if pat is not None and m.HasSubstructMatch(pat):
                        matched.append(rid)
                except Exception:
                    continue
        out.append({"type": typ, "probe": note, "matched_rules": matched,
                    "covered": bool(matched),
                    "caveat": "substructure match only; reaction-level coverage is in coverage_probes"})
    return out


# ---------------------------------------------------------------- 3 conditions × rules
def condition_matrix():
    from smartreact_engine import SmartReactEngine
    eng = SmartReactEngine(
        use_curated_templates=True,
        curated_rule_ids=_paozhi_ids(),
        use_extra_templates=False,
        use_mono_templates=False,
        use_base_templates=False,
        rescue=False,
        stereo_enum_cap=0,
        gate_conditions=True,
        strict_redox_gate=True,
    )
    out = []
    for name in CONDITIONS:
        try:
            cond = qb.RunSpec(seeds=[], cond_name=name).cond()
        except Exception as ex:
            out.append({"condition": name, "error": "%s: %s" % (type(ex).__name__, ex)})
            continue
        row = {"condition": name, "active": [], "inactive": []}
        for rid in _paozhi_ids():
            try:
                score, why = eng.cond_activation(rid, cond)
            except Exception as ex:
                row["inactive"].append({"rule": rid, "score": None,
                                        "why": "%s: %s" % (type(ex).__name__, ex)})
                continue
            item = {"rule": rid, "score": round(float(score), 3), "why": str(why)[:160]}
            (row["active"] if score > 0 else row["inactive"]).append(item)
        out.append(row)
    return out


# ---------------------------------------------------------------- 4 coverage probes
def coverage_probes():
    cur = db()
    probes = [
        ("benzylic_oxidation", "OCc1ccccc1", "O=Cc1ccccc1", "炮制·蒸制", None),
        ("benzylic_oxidation_aglycone", "OCc1ccc(O)cc1", "O=Cc1ccc(O)cc1", "炮制·蒸制", None),
        ("aromatic_o_demethylation", "COc1ccccc1", "Oc1ccccc1", "炮制·蒸制", None),
        ("aromatic_o_demethylation_catechol", "COc1ccccc1O", "Oc1ccccc1O", "炮制·蒸制", None),
        ("cyclic_ether_opening", "C1CCOC1", "OCCCCO", "炮制·醋炙", None),
        ("sugar_to_5hmf", "HBIN026793", "HBIN029444", "炮制·蒸制", None),
        ("sugar_to_maltol", "HBIN028037", "HBIN034353", "炮制·蒸制", None),
        ("oxidative_n_demethylation_aromatization", "HBIN026264", "HBIN042657", "炮制·炒黄", None),
        ("alkaloid_rearrangement", "HBIN045003", "HBIN031270", "炮制·炒黄", None),
        ("sulfite_esterification", "HBIN038606", None, "炮制·自定义", "C23H28O13S"),
    ]
    out = []
    for typ, seed, target, cond, target_formula in probes:
        if str(seed).startswith("HBIN"):
            row = db_row(cur, seed)
            if not row:
                out.append({"type": typ, "error": "seed missing %s" % seed})
                continue
            seed_name, seed_smi = row[1], row[3]
        else:
            seed_name, seed_smi = typ, seed
        tgt_smi = ""
        if str(target).startswith("HBIN"):
            row = db_row(cur, target)
            if not row:
                out.append({"type": typ, "error": "target missing %s" % target})
                continue
            tgt_smi = canon(row[3])
        elif target:
            tgt_smi = canon(target)
        try:
            hops, sec = run_once((seed_name, seed_smi, "diag"), cond_name=cond,
                                 mode="production", rounds=1)
        except Exception as ex:
            out.append({"type": typ, "error": "%s: %s" % (type(ex).__name__, ex)})
            continue
        hits = []
        for h in hops:
            if tgt_smi and canon(h.product) == tgt_smi:
                hits.append({"rule": h.rule, "co": bool(h.co), "round": h.round,
                             "formula": h.product_formula})
            elif target_formula and str(h.product_formula).upper() == target_formula.upper():
                hits.append({"rule": h.rule, "co": bool(h.co), "round": h.round,
                             "formula": h.product_formula})
        out.append({
            "type": typ, "seed": seed_name, "condition": cond,
            "target": target or target_formula,
            "n_hops": len(hops), "seconds": sec,
            "hits": hits[:8], "covered": bool(hits),
        })
    return out


def main() -> int:
    t0 = time.time()
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "holdout": holdout_matrix(),
        "rule_probes": rule_probe_matrix(),
        "conditions": condition_matrix(),
        "coverage_probes": coverage_probes(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("写出", OUT)
    print("\nholdout 分类：", dict(Counter(r["class"] for r in payload["holdout"])))
    print("\n规则探针（未覆盖=没有证据规则匹配）：")
    for r in payload["rule_probes"]:
        print("  %-38s %-8s %s" % (r["type"], "OK" if r["covered"] else "GAP",
                                   ",".join(r["matched_rules"]) or "-"))
    print("\ncoverage 探针：")
    for r in payload["coverage_probes"]:
        if r.get("error"):
            print("  %-38s ERROR %s" % (r["type"], r["error"]))
        else:
            print("  %-38s %-5s %s" % (r["type"], "HIT" if r["covered"] else "MISS",
                                       r["hits"][:2]))
    print("\n条件矩阵：")
    for r in payload["conditions"]:
        if r.get("error"):
            print("  %-12s ERROR %s" % (r["condition"], r["error"]))
        else:
            print("  %-12s active=%d inactive=%d" %
                  (r["condition"], len(r["active"]), len(r["inactive"])))
    print("\n耗时 %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
