#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""② 模板库反查：缺的产物，是「库里根本没有能产出它的模板」，还是「有模板但没匹配上」。

判断方式（对每条 miss）：
  L1  在 50,849 条模板里，挑出「产物片段是目标产物的子结构」的（rhs ⊆ want）——
      只有这些模板有可能把这对反应物变成目标产物。
  L2  把这些模板真的套到反应物上（含双底物换向），逐产物比对 canonical SMILES：
        → 有一条产出目标：`template_fires`（说明引擎的候选索引/筛选漏了）
        → 都没有：`reactant_mismatch`（模板产物侧对得上，但反应侧结构对不上）
        → L1 一条都没有：`no_template_at_all`（真缺，属数据缺口）

注意：**不能用「模板产物侧包含目标产物」判断**——模板产物侧只写变化片段，
未匹配的原子由反应物保留（例：`>>[CH3:1][C:2]` 生成的是 `CC(C)(C)C`）。

用法：
    python -I tools\\diag_miss_templates.py [--n 0] [--max-tpl 1500]
"""
from __future__ import annotations

import argparse
import itertools
import json
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
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger          # noqa: E402
from rdkit.Chem import rdChemReactions    # noqa: E402

RDLogger.DisableLog("rdApp.*")

MISS = ROOT / "reports" / "miss_diag.jsonl"
MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"
BASE = ROOT / "libs" / "smartreact" / "data" / "templates.txt"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def load_templates():
    seen, out = set(), []
    if MINED.exists():
        for line in MINED.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:                 # noqa: BLE001
                continue
            sm = (rec.get("template") or "").strip()
            if sm and sm not in seen:
                seen.add(sm)
                out.append((sm, "mined_ord"))
    if BASE.exists():
        # TSV: reaction_name / template_id / example / reaction_template / reactant_categories
        for line in BASE.open(encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            sm = parts[3].strip() if len(parts) >= 4 else ""
            if sm and ">>" in sm and sm not in seen:
                seen.add(sm)
                out.append((sm, "base"))
    return out


def build_pool():
    """[(smarts, src, rhs_query_mol)]，产物侧单片段。"""
    pool = []
    for sm, src in load_templates():
        try:
            rxn = rdChemReactions.ReactionFromSmarts(sm)
            prods = list(rxn.GetProducts())
            if len(prods) != 1:
                continue
            p = Chem.RemoveHs(Chem.Mol(prods[0]))
        except Exception:                     # noqa: BLE001
            continue
        pool.append((sm, src, p))
    return pool


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=0, help="只查前 n 条 miss（0=全部）")
    ap.add_argument("--max-tpl", type=int, default=1500, help="每条 miss 最多试多少模板")
    args = ap.parse_args()

    t0 = time.time()
    pool = build_pool()
    print("模板 %d 条（产物侧可解析、单片段）  %.1f s" % (len(pool), time.time() - t0))

    misses = [json.loads(l) for l in MISS.open(encoding="utf-8")]
    if args.n:
        misses = misses[: args.n]
    print("miss %d 条" % len(misses))

    stats = Counter()
    rows = []
    for i, m in enumerate(misses):
        want = m["want"]
        wm = Chem.MolFromSmiles(want)
        if wm is None:
            continue
        cands = [t for t in pool if t[2].GetNumAtoms() <= wm.GetNumAtoms()
                 and wm.HasSubstructMatch(t[2])]
        if not cands:
            stats["no_template_at_all"] += 1
            rows.append({"i": i, "want": want, "verdict": "no_template_at_all", "n": 0})
            continue
        subs = [Chem.MolFromSmiles(s) for s in m["reactants"]]
        subs = [s for s in subs if s is not None]
        fired, hit_rule = False, ""
        for sm, src, _p in cands[: args.max_tpl]:
            try:
                rxn = rdChemReactions.ReactionFromSmarts(sm)
            except Exception:                 # noqa: BLE001
                continue
            for order in itertools.permutations(range(len(subs)),
                                                min(len(subs), 3)):
                try:
                    outs = rxn.RunReactants(tuple(subs[k] for k in order))
                except Exception:             # noqa: BLE001
                    continue
                for tup in outs:
                    for mol in tup:
                        try:
                            Chem.SanitizeMol(mol)
                            cs = Chem.MolToSmiles(mol)
                        except Exception:     # noqa: BLE001
                            continue
                        if cs == want:
                            fired, hit_rule = True, sm
                            break
                    if fired:
                        break
                if fired:
                    break
            if fired:
                break
        verdict = "template_fires" if fired else "reactant_mismatch"
        stats[verdict] += 1
        rows.append({"i": i, "want": want, "verdict": verdict,
                     "n": len(cands), "rule": hit_rule})
        if (i + 1) % 20 == 0:
            print("  ...%d/%d  %.0f s  %s" % (i + 1, len(misses), time.time() - t0,
                                              dict(stats)))

    n = max(1, len(misses))
    print("\n模板反查（%.0f s）：" % (time.time() - t0))
    for k, v in stats.most_common():
        print("  %-22s %3d 条（%.1f%%）" % (k, v, 100.0 * v / n))

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_templates": len(pool),
        "n_miss": len(misses),
        "stats": dict(stats),
        "rows": rows,
    }
    p = ROOT / "reports" / "miss_templates_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
