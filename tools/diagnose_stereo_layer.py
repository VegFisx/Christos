# -*- coding: utf-8 -*-
"""为什么只有槲皮素案例拿到 exact stereo？

对五个案例都用 PubChem 的立体结构（isomeric SMILES）作底物重跑当前引擎，
只保留与参考产物在连接层一致的候选，统计这些候选自身带几个手性中心、
其中几个被指定。用来判断 exact stereo 失败是"候选结构没带立体信息"，
还是"带了但配错"。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path("D:/ProgramData/DSHNS/chemreact-staging")
for _p in (STAGE / "core", STAGE / "rules", STAGE / "libs", STAGE / "tools",
           STAGE / "sources", STAGE / "conditions"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
import query_base as qb

RDLogger.DisableLog("rdApp.*")

PUBCHEM = STAGE / "reports" / "paper" / "pubchem_literature_validation_20261030.json"
OUT_JSON = STAGE / "reports" / "paper" / "stereo_diagnostic_20261030.json"
OUT_MD = STAGE / "reports" / "paper" / "stereo_diagnostic_20261030.md"

CASES = [
    ("glycyrrhizic_acid", "Glycyrrhizic acid", "18beta-Glycyrrhetinic acid"),
    ("ginsenoside_rb1_rg3", "Ginsenoside Rb1", "20(S)-Ginsenoside Rg3"),
    ("aconitine_benzoylaconine", "Aconitine", "Benzoylaconine"),
    ("benzoylaconine_aconine", "Benzoylaconine", "Aconine"),
    ("rutin_quercetin", "Rutin", "Quercetin"),
]


def full_inchikey(smiles):
    mol = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToInchiKey(mol) if mol else ""


def connectivity_key(inchikey):
    return (inchikey or "").split("-", 1)[0]


def canon(smiles):
    mol = Chem.MolFromSmiles(smiles or "")
    return Chem.MolToSmiles(mol, isomericSmiles=True) if mol else ""


def stereo_counts(smiles):
    mol = Chem.MolFromSmiles(smiles or "")
    if mol is None:
        return None
    centers = Chem.FindMolChiralCenters(
        mol, includeUnassigned=True, useLegacyImplementation=False)
    specified = sum(1 for _i, tag in centers if tag != "?")
    tags = sorted({"?" if tag == "?" else tag for _i, tag in centers})
    return {"n_centres": len(centers), "n_specified": specified,
            "tags": tags, "has_at": "@" in (smiles or "")}


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


def main():
    data = json.loads(PUBCHEM.read_text(encoding="utf-8"))
    refs = {r["query"]: r for r in data.get("records", [])}
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "purpose": "Diagnose why only one of five cases reaches an exact "
                      "stereochemical match when PubChem isomeric structures "
                      "are used.",
           "cases": []}
    for key, sub_name, prod_name in CASES:
        sub = refs[sub_name]
        prod = refs[prod_name]
        sub_smiles = sub.get("isomeric_smiles") or ""
        prod_smiles = prod.get("isomeric_smiles") or ""
        target_conn = connectivity_key(prod.get("inchikey", ""))
        target_canon = canon(prod_smiles)
        inv, seconds = run_one((sub_name, sub_smiles, "PubChem:stereo-diagnostic"))
        rows = []
        for p in inv.paths:
            ps = p.get("product_smiles", "")
            if connectivity_key(full_inchikey(ps)) != target_conn:
                continue
            rows.append({
                "rule": p.get("rule_name"),
                "exact": canon(ps) == target_canon,
                "candidate_inchikey": full_inchikey(ps),
                "candidate_stereo": stereo_counts(ps),
                "candidate_smiles": ps,
            })
        exact = [r for r in rows if r["exact"]]
        entry = {
            "key": key,
            "substrate": sub_name,
            "product": prod_name,
            "substrate_cid": sub.get("cid"),
            "substrate_inchikey": sub.get("inchikey"),
            "substrate_stereo": stereo_counts(sub_smiles),
            "product_cid": prod.get("cid"),
            "product_inchikey": prod.get("inchikey"),
            "product_stereo": stereo_counts(prod_smiles),
            "n_candidates": len(inv.paths),
            "n_connectivity_hits": len(rows),
            "n_exact": len(exact),
            "connectivity_hits": rows[:5],
            "seconds": seconds,
        }
        out["cases"].append(entry)
        print("%-28s cand=%3d conn=%2d exact=%d target_centres=%s cand_max_specified=%s" % (
            key, len(inv.paths), len(rows), len(exact),
            (stereo_counts(prod_smiles) or {}).get("n_centres"),
            max([(r["candidate_stereo"] or {}).get("n_specified", -1) for r in rows] or [-1])))
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    sep = chr(10)
    lines = [
        "# 立体层诊断：为什么只有槲皮素案例拿到 exact stereo",
        "",
        "生成时间：" + out["generated_at"],
        "",
        "做法：五个案例都用 PubChem 的 isomeric SMILES 作底物，按与文献一致性验证相同的运行配置（煎煮、100 C、60 min、pH 6.5、空气、一轮、cap 64/pair、strict_redox_gate）重跑当前引擎；只统计与 PubChem 参考产物在连接层一致的候选，检查候选自身的手性中心数与已指定数。",
        "",
        "| 案例 | 参考产物手性中心/已指定 | 候选最大已指定数 | 连接层候选 | exact |",
        "|---|---:|---:|---:|---:|",
    ]
    for c in out["cases"]:
        tgt = c["product_stereo"] or {}
        max_spec = max([(r["candidate_stereo"] or {}).get("n_specified", -1)
                        for r in c["connectivity_hits"]] or [-1])
        lines.append("| %s | %s/%s | %s | %d | %d |" % (
            c["product"], tgt.get("n_centres"), tgt.get("n_specified"),
            max_spec, c["n_connectivity_hits"], c["n_exact"]))
    lines += [
        "",
        "判定口径：连接层一致 = InChIKey 第一段相同；exact = isomeric SMILES 规范化后与 PubChem 参考产物完全相同；“已指定”用 RDKit FindMolChiralCenters(includeUnassigned=True) 统计，tag 不是 ? 才算指定。",
        "",
        "逐案例细节见同目录 JSON。",
    ]
    OUT_MD.write_text(sep.join(lines) + sep, encoding="utf-8")
    print("wrote", OUT_JSON)
    print("wrote", OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
