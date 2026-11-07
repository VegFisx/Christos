# -*- coding: utf-8 -*-
"""模板-测试同源性分析（第 105 轮，A3）。

问题：模板来自 ORD、测试来自 USPTO-50k，严格同反应 0 条（第 94 轮），
但审稿人会问「模板是不是记住了近乎相同的底物」。
做法：对每条测试反应，算它的每个反应物分子在**模板示例反应物**里的最近邻相似度
（Morgan r=2, 2048 bit, Tanimoto），报告分布与覆盖率。

只读数据，不跑引擎。
"""
from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, DataStructs

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "libs" / "smartreact" / "data" / "templates.txt"
DATA = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
OUT = ROOT / "reports" / "template_similarity_20261105.json"


def fp_of(smi: str):
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)


def side0(s: str):
    if not s:
        return []
    s = s.split(">")[0]
    return [x for x in s.split(".") if x]


def load_template_fps():
    fps = []
    with io.open(TPL, encoding="utf-8") as f:
        for line in f:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            for smi in side0(cols[2]):
                fp = fp_of(smi)
                if fp is not None:
                    fps.append(fp)
    return fps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    tpl_fps = load_template_fps()
    print("模板示例反应物分子：%d 个指纹" % len(tpl_fps))

    import random

    rows = []
    with io.open(DATA, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    random.Random(a.seed).shuffle(rows)
    rows = rows[: a.n]
    print("测试反应：%d 条（seed %d）" % (len(rows), a.seed))

    best_per_reaction = []
    covered_70 = covered_85 = 0
    per_mol_stats = []
    for i, r in enumerate(rows):
        rs = r.get("reactants") or []
        if isinstance(rs, str):
            rs = [x for x in rs.split(".") if x]
        mol_bests = []
        for smi in rs:
            fp = fp_of(smi)
            if fp is None:
                continue
            sims = DataStructs.BulkTanimotoSimilarity(fp, tpl_fps)
            mol_bests.append(max(sims) if sims else 0.0)
        if not mol_bests:
            continue
        per_mol_stats.extend(mol_bests)
        best_per_reaction.append(max(mol_bests))
        if min(mol_bests) >= 0.70:
            covered_70 += 1
        if min(mol_bests) >= 0.85:
            covered_85 += 1
        if (i + 1) % 500 == 0:
            print("  ...%d/%d" % (i + 1, len(rows)))

    def dist(vals):
        vals = sorted(vals)
        if not vals:
            return {}
        def q(p):
            k = max(0, min(len(vals) - 1, int(round(p * (len(vals) - 1)))))
            return round(vals[k], 4)
        return {
            "n": len(vals),
            "median": round(statistics.median(vals), 4),
            "p10": q(0.10), "p90": q(0.90), "p99": q(0.99),
            "frac_ge_0.9": round(sum(1 for v in vals if v >= 0.9) / len(vals), 4),
            "frac_ge_0.7": round(sum(1 for v in vals if v >= 0.7) / len(vals), 4),
            "frac_eq_1.0": round(sum(1 for v in vals if v >= 0.9999) / len(vals), 4),
        }

    summary = {
        "generated_at": "2026-11-05",
        "n_templates_molecules": len(tpl_fps),
        "n_reactions": len(rows),
        "seed": a.seed,
        "nearest_template_molecule_similarity": dist(per_mol_stats),
        "reaction_max_similarity": dist(best_per_reaction),
        "reaction_all_reactants_ge_0.70": covered_70,
        "reaction_all_reactants_ge_0.85": covered_85,
        "reaction_all_reactants_ge_0.70_frac": round(covered_70 / max(1, len(best_per_reaction)), 4),
        "reaction_all_reactants_ge_0.85_frac": round(covered_85 / max(1, len(best_per_reaction)), 4),
    }
    Path(a.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("写出 %s" % a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
