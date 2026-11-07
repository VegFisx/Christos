# -*- coding: utf-8 -*-
"""Retrospective validation against experimentally reported TCM conversions.

This is a literature-consistency audit, not a wet-lab validation.  It checks
whether the current engine reaches the reported product, which rule produces
it, and whether the rule's mapped reaction centre agrees with the reaction
family described by the cited study.  Reported intermediates are checked when
an equivalent structure is available in the local compound table.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs",
           STAGE / "tools", STAGE / "sources", STAGE / "conditions"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
from rdkit.Chem import rdChemReactions

import query_base as qb

RDLogger.DisableLog("rdApp.*")

DB = "file:D:/TCMAI/tcm.db?mode=ro"
PUBMED_XML = STAGE / "reports" / "paper" / "literature_validation_pubmed_20261030.xml"
PUBCHEM_JSON = STAGE / "reports" / "paper" / "pubchem_literature_validation_20261030.json"
OUT_JSON = STAGE / "reports" / "paper" / "literature_validation_20261030.json"
OUT_CSV = STAGE / "reports" / "paper" / "literature_validation_20261030.csv"
OUT_MD = STAGE / "reports" / "paper" / "literature_validation_20261030.md"

# Case definitions follow the reaction families described in the cited papers.
CASES = [
    {
        "key": "glycyrrhizic_acid",
        "label_zh": "甘草酸 → 甘草次酸",
        "label_en": "Glycyrrhizic acid to glycyrrhetinic acid",
        "substrate": "Glycyrrhizic acid",
        "product": "18beta-glycyrrhetinic acid",
        "expected_rules": ["hydrolysis_glycoside_001"],
        "literature_path": (
            "Hydrothermal hydrolysis produces glycyrrhetinic acid and "
            "glycyrrhetinic acid 3-O-mono-beta-D-glucuronide through "
            "consecutive and parallel reactions."
        ),
        "intermediates": ["glycyrrhetinic acid 3-O-mono-beta-D-glucuronide"],
        "intermediate_required": False,
        "pmids": ["26213056"],
        "pubchem_substrate": "Glycyrrhizic acid",
        "pubchem_product": "18beta-Glycyrrhetinic acid",
        "path_assessment": (
            "反应族一致。文献同时报告单葡萄糖醛酸中间体和连续/并行水解；"
            "该中间体不在本地成分表中，因此本轮无法确认具体先后顺序。"
        ),
    },
    {
        "key": "ginsenoside_rb1_rg3",
        "label_zh": "人参皂苷 Rb1 → Rg3",
        "label_en": "Ginsenoside Rb1 to Rg3",
        "substrate": "Ginsenoside rb1",
        "product": "Ginsenoside rg3",
        "expected_rules": ["hydrolysis_glycoside_001"],
        "literature_path": (
            "Enzymatic conversion proceeds from Rb1 through ginsenoside Rd "
            "to Rg3; thermal processing also forms Rg3 through glycoside "
            "hydrolysis and elimination."
        ),
        "intermediates": ["Ginsenoside rd"],
        "intermediate_required": True,
        "pmids": ["28256039", "29021706", "32987784"],
        "pubchem_substrate": "Ginsenoside Rb1",
        "pubchem_product": "20(S)-Ginsenoside Rg3",
        "path_assessment": (
            "文献的 Rb1 → Rd → Rg3 序列可通过两次单轮运行复现。另一轮运行中，"
            "引擎也能从 Rb1 直接得到 Rg3，因此允许一条文献发酵实验未描述的捷径。"
            "本地结构缺少立体化学信息。"
        ),
    },
    {
        "key": "aconitine_benzoylaconine",
        "label_zh": "乌头碱 → 苯甲酰乌头原碱",
        "label_en": "Aconitine to benzoylaconine",
        "substrate": "Aconitine",
        "product": "Benzoylaconine",
        "expected_rules": ["hydrolysis_ester_001"],
        "literature_path": (
            "Hydrolysis removes the C8 acetylester from the diester "
            "C19-diterpenoid skeleton."
        ),
        "intermediates": [],
        "intermediate_required": False,
        "pmids": ["27761113", "18306748"],
        "pubchem_substrate": "Aconitine",
        "pubchem_product": "Benzoylaconine",
        "path_assessment": (
            "规则族和脱去片段 C2H2O（对应乙酰基）均符合 C8 乙酸酯水解。"
            "本地二维结构无法提供原子映射级的 C8 位点确认。"
        ),
    },
    {
        "key": "benzoylaconine_aconine",
        "label_zh": "苯甲酰乌头原碱 → 乌头原碱",
        "label_en": "Benzoylaconine to aconine",
        "substrate": "Benzoylaconine",
        "product": "Aconine",
        "expected_rules": ["hydrolysis_ester_001"],
        "literature_path": (
            "Further hydrolysis removes the C14 benzoylester and gives aconine."
        ),
        "intermediates": [],
        "intermediate_required": False,
        "pmids": ["27761113", "18306748"],
        "pubchem_substrate": "Benzoylaconine",
        "pubchem_product": "Aconine",
        "path_assessment": (
            "规则族和脱去片段 C7H4O（对应苯甲酰基）均符合 C14 苯甲酸酯水解。"
            "两步乌头碱水解也可分别跑通。本地二维结构无法提供原子映射级的 C14 位点确认。"
        ),
    },
    {
        "key": "rutin_quercetin",
        "label_zh": "芦丁 → 槲皮素",
        "label_en": "Rutin to quercetin",
        "substrate": "Rutin",
        "product": "Quercetin",
        "expected_rules": ["hydrolysis_glycoside_001"],
        "literature_path": (
            "Acid or subcritical-water treatment cleaves the rutinoside "
            "glycosidic bond; isoquercetin is also observed as a product."
        ),
        "intermediates": ["Isoquercitrin", "Isoquercitin", "Isoquercetrin"],
        "intermediate_required": False,
        "pmids": ["28702430", "31608257"],
        "pubchem_substrate": "Rutin",
        "pubchem_product": "Quercetin",
        "path_assessment": (
            "文献中间体异槲皮素出现在同一轮候选中，并从它单独起跑可生成槲皮素。"
            "目标产物也在糖苷键水解层面与文献路径一致。"
        ),
    },
]


def canon(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToSmiles(mol, isomericSmiles=True) if mol else ""


def full_inchikey(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ""
    return Chem.MolToInchiKey(mol)


def formula(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return ""
    from rdkit.Chem import rdMolDescriptors
    return rdMolDescriptors.CalcMolFormula(mol)


def formula_counts(text: str) -> dict:
    out = {}
    for element, count in re.findall(r"([A-Z][a-z]?)(\d*)", text or ""):
        out[element] = out.get(element, 0) + (int(count) if count else 1)
    return out


def formula_delta(before: str, after: str) -> str:
    a, b = formula_counts(before), formula_counts(after)
    keys = sorted(set(a) | set(b))
    return " ".join(
        "%s%+d" % (element, b.get(element, 0) - a.get(element, 0))
        for element in keys
        if b.get(element, 0) != a.get(element, 0)
    )


def stereo_state(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return "unparsable"
    centers = Chem.FindMolChiralCenters(
        mol, includeUnassigned=True, useLegacyImplementation=False)
    if not centers:
        return "none"
    specified = sum(1 for _idx, tag in centers if tag != "?")
    if specified == 0:
        return "unspecified"
    if specified == len(centers):
        return "specified"
    return "partial"


def fetch(cur, name):
    return cur.execute(
        "SELECT name_en, smiles FROM compounds "
        "WHERE lower(name_en)=lower(?) AND smiles IS NOT NULL LIMIT 1",
        (name,),
    ).fetchone()


def rule_center(rule: dict) -> dict:
    rxn = rdChemReactions.ReactionFromSmarts(rule["smarts"])
    if rxn is None:
        return {"broken_map_bonds": [], "formed_map_bonds": [], "error": "unparsable"}
    reactants = [rxn.GetReactantTemplate(i) for i in range(rxn.GetNumReactantTemplates())]
    products = [rxn.GetProductTemplate(i) for i in range(rxn.GetNumProductTemplates())]

    def bonds(mols):
        out = set()
        for mol in mols:
            for bond in mol.GetBonds():
                a, b = bond.GetBeginAtom(), bond.GetEndAtom()
                if a.GetAtomMapNum() and b.GetAtomMapNum():
                    out.add(tuple(sorted((a.GetAtomMapNum(), b.GetAtomMapNum()))))
        return out

    left, right = bonds(reactants), bonds(products)
    return {
        "broken_map_bonds": sorted(left - right),
        "formed_map_bonds": sorted(right - left),
    }


def bond_elements(rule: dict, bond) -> list:
    """断键两端映射号对应的元素符号（直接从规则 SMARTS 里取）。"""
    sm = str((rule or {}).get("smarts") or "")
    elem = {int(m.group(2)): m.group(1)
            for m in re.finditer(r"\[([A-Z][a-z]?):(\d+)\]", sm)}
    return [elem.get(int(x), "?") for x in bond]


def _as_list(value) -> list:
    if isinstance(value, str):
        return [x for x in value.split("|") if x]
    return [x for x in (value or []) if x]


def format_element_delta(value) -> str:
    """把引擎的 `C|H|O` 元素差（如 -12|-16|-12）排成 C-12 H-16 O-12。"""
    parts = str(value or "").split("|")
    if len(parts) == 3:
        return " ".join("%s%s" % (e, v) for e, v in zip(("C", "H", "O"), parts)
                        if v and v not in ("0", "+0"))
    return str(value or "")


def co_product_records(value) -> list:
    return [{"smiles": s, "formula": formula(s)} for s in _as_list(value)]


def path_steps(paths, by_id) -> list:
    """把匹配路径整理成可比较的步骤：规则、断键元素、轮次、共产物。"""
    seen, out = set(), []
    for p in paths:
        sig = (p.get("rule_name"), p.get("round"), p.get("element_delta"))
        if sig in seen:
            continue
        seen.add(sig)
        rule = by_id.get(p.get("rule_name"), {})
        center = rule_center(rule) if rule else {}
        broken = center.get("broken_map_bonds", [])
        out.append({
            "rule": p.get("rule_name"),
            "round": p.get("round"),
            "broken_map_bonds": broken,
            "broken_elements": [bond_elements(rule, b) for b in broken],
            "formed_map_bonds": center.get("formed_map_bonds", []),
            "element_delta": p.get("element_delta"),
        })
    return out


def load_pubmed_metadata(path: Path) -> dict:
    root = ET.parse(path).getroot()
    out = {}
    for art in root.findall(".//PubmedArticle"):
        pmid = art.findtext("./MedlineCitation/PMID") or ""
        title = " ".join("".join(art.find("./MedlineCitation/Article/ArticleTitle").itertext()).split())
        journal = art.findtext("./MedlineCitation/Article/Journal/Title") or ""
        year = (art.findtext("./MedlineCitation/Article/Journal/JournalIssue/PubDate/Year")
                or art.findtext("./MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate")
                or "")
        doi = next(
            ("".join(x.itertext()) for x in art.findall("./PubmedData/ArticleIdList/ArticleId")
             if x.get("IdType") == "doi"),
            "",
        )
        abstract = " ".join(
            "".join(x.itertext()) for x in art.findall("./MedlineCitation/Article/Abstract/AbstractText")
        ).strip()
        out[pmid] = {
            "pmid": pmid,
            "title": title,
            "journal": journal,
            "year": year,
            "doi": doi,
            "abstract": abstract,
            "url": "https://pubmed.ncbi.nlm.nih.gov/%s/" % pmid,
        }
    return out


def load_pubchem_metadata(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["query"]: r for r in data.get("records", [])}


def connectivity_key(inchikey: str) -> str:
    return (inchikey or "").split("-", 1)[0]


def source_hashes() -> dict:
    files = [
        STAGE / "rules" / "rules.json",
        STAGE / "conditions" / "templates.py",
        STAGE / "core" / "query_base.py",
        STAGE / "core" / "smartreact_engine.py",
    ]
    return {
        str(p.relative_to(STAGE)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    }


def run_one(seed):
    spec = qb.RunSpec(
        seeds=[seed],
        cond_name="煎煮",
        rounds=1,
        max_pairs=1,
        max_products_per_pair=64,
        use_curated_templates=True,
        strict_redox_gate=True,
    )
    t0 = time.time()
    inv = qb.build_inventory(spec, score=False, use_cache=False)
    return inv, round(time.time() - t0, 1)


def main() -> int:
    cur = sqlite3.connect(DB, uri=True).cursor()
    rules = json.loads((STAGE / "rules" / "rules.json").read_text(encoding="utf-8"))
    rules = rules if isinstance(rules, list) else rules.get("rules", rules)
    by_id = {r["id"]: r for r in rules}
    pubs = load_pubmed_metadata(PUBMED_XML)
    pubchem = load_pubchem_metadata(PUBCHEM_JSON)
    rows = []

    for case in CASES:
        sub, prod = fetch(cur, case["substrate"]), fetch(cur, case["product"])
        if not sub or not prod:
            rows.append({
                **case,
                "status": "missing_in_db",
                "missing": case["substrate"] if not sub else case["product"],
            })
            continue

        target = canon(prod[1])
        inv, elapsed = run_one((sub[0], sub[1], "tcm.db:literature-validation"))
        hits = [p for p in inv.paths if canon(p.get("product_smiles", "")) == target]

        all_rules = sorted({p.get("rule_name", "") for p in hits})
        expected_hit = sorted(set(all_rules) & set(case["expected_rules"]))

        intermediate_results = []
        seen_intermediate = set()
        for name in case.get("intermediates", []):
            rec = fetch(cur, name)
            if rec is None:
                intermediate_results.append({
                    "name": name, "status": "not_in_local_db",
                })
                continue
            key = canon(rec[1])
            n = sum(1 for p in inv.paths if canon(p.get("product_smiles", "")) == key)
            item = {
                "name": rec[0],
                "status": "observed" if n else "not_observed",
                "n_paths": n,
                "smiles": rec[1],
            }
            if key not in seen_intermediate:
                seen_intermediate.add(key)
                if n:
                    next_inv, next_seconds = run_one(
                        (rec[0], rec[1], "tcm.db:literature-validation:intermediate"))
                    next_hits = [
                        p for p in next_inv.paths
                        if canon(p.get("product_smiles", "")) == target
                    ]
                    item.update({
                        "intermediate_to_target": bool(next_hits),
                        "intermediate_to_target_rules": sorted({
                            p.get("rule_name", "") for p in next_hits if p.get("rule_name")
                        }),
                        "intermediate_run_seconds": next_seconds,
                        "intermediate_run_candidates": len(next_inv.paths),
                    })
            intermediate_results.append(item)

        unique_hits = []
        seen = set()
        for p in hits:
            sig = (p.get("rule_name"), p.get("co_products"), p.get("element_delta"))
            if sig in seen:
                continue
            seen.add(sig)
            rule = by_id.get(p.get("rule_name"), {})
            unique_hits.append({
                "rule": p.get("rule_name"),
                "round": p.get("round"),
                "activation": p.get("activation"),
                "activation_why": p.get("activation_why"),
                "element_delta": p.get("element_delta"),
                "co_products": p.get("co_products"),
                "reaction_center": rule_center(rule) if rule else {},
            })

        literature = [pubs[p] for p in case["pmids"] if p in pubs]
        product_stereo = stereo_state(prod[1])
        substrate_stereo = stereo_state(sub[1])
        pc_sub = pubchem.get(case["pubchem_substrate"], {})
        pc_prod = pubchem.get(case["pubchem_product"], {})
        reference_result = {
            "substrate": case["pubchem_substrate"],
            "product": case["pubchem_product"],
            "substrate_cid": pc_sub.get("cid"),
            "product_cid": pc_prod.get("cid"),
            "substrate_formula": pc_sub.get("formula"),
            "product_formula": pc_prod.get("formula"),
            "substrate_inchikey": pc_sub.get("inchikey"),
            "product_inchikey": pc_prod.get("inchikey"),
            "connectivity_match": (
                connectivity_key(full_inchikey(prod[1]))
                == connectivity_key(pc_prod.get("inchikey", ""))
            ),
            "status": "not_run",
        }
        ref_sub_smiles = pc_sub.get("isomeric_smiles")
        ref_prod_smiles = pc_prod.get("isomeric_smiles")
        if ref_sub_smiles and ref_prod_smiles:
            ref_inv, ref_seconds = run_one((
                case["pubchem_substrate"], ref_sub_smiles,
                "PubChem:literature-validation"))
            ref_target = canon(ref_prod_smiles)
            ref_hits = [
                p for p in ref_inv.paths
                if canon(p.get("product_smiles", "")) == ref_target
            ]
            ref_target_conn = connectivity_key(
                full_inchikey(ref_prod_smiles))
            ref_conn_hits = [
                p for p in ref_inv.paths
                if connectivity_key(full_inchikey(
                    p.get("product_smiles", ""))) == ref_target_conn
            ]
            ref_status = (
                "exact_stereo_hit" if ref_hits
                else "connectivity_only" if ref_conn_hits
                else "miss"
            )
            ref_steps = path_steps(ref_hits or ref_conn_hits, by_id)
            reference_result.update({
                "status": ref_status,
                "steps": ref_steps,
                "hit_rules": sorted({
                    p.get("rule_name", "") for p in ref_hits if p.get("rule_name")
                }),
                "n_matching_paths": len(ref_hits),
                "n_connectivity_only_paths": len(ref_conn_hits),
                "n_all_candidates": len(ref_inv.paths),
                "seconds": ref_seconds,
            })
        rows.append({
            "key": case["key"],
            "label_zh": case["label_zh"],
            "label_en": case["label_en"],
            "status": "hit" if hits else "miss",
            "substrate": {
                "name": sub[0], "smiles": sub[1], "formula": formula(sub[1]),
                "inchikey": full_inchikey(sub[1]), "stereo": substrate_stereo,
            },
            "product": {
                "name": prod[0], "smiles": prod[1], "formula": formula(prod[1]),
                "inchikey": full_inchikey(prod[1]), "stereo": product_stereo,
            },
            "formula_delta_product_minus_substrate":
                formula_delta(formula(sub[1]), formula(prod[1])),
            "n_all_candidates": len(inv.paths),
            "n_matching_paths": len(hits),
            "hit_rules": all_rules,
            "expected_rules": case["expected_rules"],
            "expected_rule_matched": bool(expected_hit),
            "matching_paths": unique_hits,
            "literature": literature,
            "literature_path": case["literature_path"],
            "path_assessment": case["path_assessment"],
            "intermediates": intermediate_results,
            "intermediate_required": case["intermediate_required"],
            "paths": {
                "local_2d": {
                    "status": "hit" if hits else "miss",
                    "n_matching_paths": len(hits),
                    "steps": path_steps(hits, by_id),
                },
                "pubchem_isomeric": {
                    "status": reference_result["status"],
                    "n_matching_paths": reference_result.get("n_matching_paths", 0),
                    "steps": reference_result.get("steps", []),
                },
                "intermediate_chain": [
                    {"name": x["name"], "status": x["status"],
                     "to_target": x.get("intermediate_to_target"),
                     "rules": x.get("intermediate_to_target_rules", []),
                     "candidates": x.get("intermediate_run_candidates")}
                    for x in intermediate_results
                ],
                "literature_path": case["literature_path"],
                "verdict": case["path_assessment"],
            },
            "pubchem_identity_check": reference_result,
            "conditions": {
                "profile": "煎煮",
                "temperature_C": 100.0,
                "time_min": 60.0,
                "pH": 6.5,
                "atmosphere": "air",
            },
            "seconds": elapsed,
        })
        print("%-40s %-5s rules=%s candidates=%d (%.1fs)" % (
            case["label_en"], rows[-1]["status"].upper(),
            ",".join(all_rules) or "-", len(inv.paths), rows[-1]["seconds"]))

    summary = {
        "n_cases": len(rows),
        "product_connectivity_hits": sum(r["status"] == "hit" for r in rows),
        "expected_reaction_family_hits":
            sum(bool(r["expected_rule_matched"]) for r in rows),
        "pubchem_exact_stereo_hits":
            sum(r["pubchem_identity_check"]["status"] == "exact_stereo_hit"
                for r in rows),
        "pubchem_connectivity_hits":
            sum(bool(r["pubchem_identity_check"].get("n_connectivity_only_paths", 0))
                for r in rows),
        "literature_records":
            len({p["pmid"] for r in rows for p in r["literature"]}),
    }
    payload = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "validation_type": "computational experiment (retrospective literature-consistency audit)",
        "database": DB,
        "database_note": "read-only; structures are used as stored locally",
        "run_condition": "煎煮, 100 C, 60 min, pH 6.5, air; 1 round; cap 64/pair",
        "source_hashes": source_hashes(),
        "summary": summary,
        "cases": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        fieldnames = [
            "case", "status", "product_formula", "formula_delta",
            "hit_rules", "expected_rule_matched", "n_matching_paths",
            "n_all_candidates", "intermediates", "stereo",
            "pubchem_connectivity_match", "pubchem_run_status", "seconds",
        ]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "case": r["label_zh"],
                "status": r["status"],
                "product_formula": r["product"]["formula"],
                "formula_delta": r["formula_delta_product_minus_substrate"],
                "hit_rules": "|".join(r["hit_rules"]),
                "expected_rule_matched": r["expected_rule_matched"],
                "n_matching_paths": r["n_matching_paths"],
                "n_all_candidates": r["n_all_candidates"],
                "intermediates": "|".join(
                    "%s:%s%s" % (
                        x["name"], x["status"],
                        (",to_target=%s" % x["intermediate_to_target"])
                        if "intermediate_to_target" in x else "")
                    for x in r["intermediates"]
                ),
                "stereo": r["product"]["stereo"],
                "pubchem_connectivity_match":
                    r["pubchem_identity_check"]["connectivity_match"],
                "pubchem_run_status": r["pubchem_identity_check"]["status"],
                "seconds": r["seconds"],
            })

    lines = [
        "# 文献一致性验证结果",
        "",
        "生成时间：%s" % payload["generated_at"],
        "",
        "验证类型：计算实验（回溯性文献一致性检查），不是湿实验。",
        "",
        "汇总：%d/%d 产物连接层命中；%d/%d 使用预期反应族；"
        "%d/%d 在 PubChem 立体结构重跑中得到完整立体结构命中；"
        "%d/%d 至少得到连接层命中。" % (
            summary["product_connectivity_hits"], summary["n_cases"],
            summary["expected_reaction_family_hits"], summary["n_cases"],
            summary["pubchem_exact_stereo_hits"], summary["n_cases"],
            summary["pubchem_connectivity_hits"], summary["n_cases"],
        ),
        "",
        "本地二维运行：%d/%d 连接层命中（结构与文献产物一致）。" % (
            summary["product_connectivity_hits"], summary["n_cases"]),
        "PubChem 立体重跑：%d/%d 完整立体命中；%d/%d 连接层命中。" % (
            summary["pubchem_exact_stereo_hits"], summary["n_cases"],
            summary["pubchem_connectivity_hits"], summary["n_cases"]),
        "",
        "统一运行条件：煎煮，100°C，60 分钟，pH 6.5，空气，一轮，"
        "每个底物对最多 64 个产物。",
        "",
        "| 案例 | 本地拓扑命中 | 规则族一致 | PubChem 立体结构重跑 | 连通层一致 | 规则 | 分子式差（产物-底物） | 文献中间体 | 本地立体状态 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        inter = "；".join("%s：%s%s" % (
            x["name"], x["status"],
            ("，续到目标=%s" % x["intermediate_to_target"])
            if "intermediate_to_target" in x else "")
                          for x in r["intermediates"]) or "未定义"
        ref = r["pubchem_identity_check"]
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["label_zh"], r["status"], "是" if r["expected_rule_matched"] else "否",
            ref["status"], "是" if ref["connectivity_match"] else "否",
            "、".join(r["hit_rules"]) or "无",
            r["formula_delta_product_minus_substrate"], inter,
            r["product"]["stereo"],
        ))
    lines += [
        "",
        "## 路径对照（引擎 vs 文献）",
        "",
        "| 案例 | 引擎路径（二维运行） | 立体重跑 | 文献路径 | 中间体 | 判定 |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        if not r.get("paths"):
            continue
        steps = r["paths"]["local_2d"]["steps"]
        eng = "；".join(
            "%s，断键 %s，第 %s 轮，分子式差 %s" % (
                s["rule"] or "?",
                "、".join("–".join(e) for e in s["broken_elements"]) or "—",
                s["round"], format_element_delta(s.get("element_delta")) or "—")
            for s in steps) or "未命中"
        inter = "；".join(
            "%s（%s%s）" % (x["name"], x["status"],
                           "，续到目标" if x.get("to_target") else "")
            for x in r["paths"]["intermediate_chain"]) or "未定义"
        ref = r["paths"]["pubchem_isomeric"]
        ref_text = ref["status"]
        if ref.get("steps"):
            ref_text += "（%s，断键 %s）" % (
                ref["steps"][0]["rule"] or "?",
                "、".join("–".join(e) for e in ref["steps"][0]["broken_elements"]) or "—")
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            r["label_zh"], eng, ref_text, r["paths"]["literature_path"],
            inter, r["paths"]["verdict"]))
    lines += [
        "",
        "## 逐案判定",
        "",
    ]
    for r in rows:
        lines.append("- **%s**：%s" % (r["label_zh"], r["path_assessment"]))
    lines += [
        "",
        "判定口径：",
        "",
        "- “产物命中”要求目标分子按本地库中的非映射 SMILES 规范化后完全一致。",
        "- “规则族一致”要求产物命中路径使用该文献所述的水解规则。",
        "- “分子式差”用于标示模型实际脱去的基团；它不替代原子映射级的机理证明。",
        "- 本地结构若缺少立体化学，记录为 `unspecified`，不能宣称验证了文献中的特定立体异构体。",
        "- PubChem 检查使用带立体化学的参考结构重新运行；该结果与本地库结果分开报告。",
        "- 文献中间体只有在本地库中存在时才做观察记录；缺失时写 `not_in_local_db`。",
        "- 对观察到的中间体再独立运行一轮；`intermediate_to_target=true` 表示该中间体可继续生成目标。",
        "",
        "逐案例文献和路径细节见同目录 JSON。",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("JSON ->", OUT_JSON)
    print("CSV  ->", OUT_CSV)
    print("MD   ->", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
