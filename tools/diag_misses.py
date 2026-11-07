#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""缺产物归因：把「登记产物没出现在候选里」的反应捞出来，并自动分四类。

为什么要分：8% 的缺口里，不同原因要不同对策——
  技术性（立构/互变）  → 改评测口径或规范化，不用补化学
  同分子式异构        → 模板走偏，可能定错结构
  两步可达            → 基准只跑 1 轮，跑 2 轮就能补上
  真缺模板            → 才是要补数据/规则的

用法：
    python -I tools\\diag_misses.py --n 3000 --probe 50
"""
from __future__ import annotations

import argparse
import ast
import json
import random
import statistics
import sys
import time
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

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem import rdMolDescriptors  # noqa: E402

RDLogger.DisableLog("rdApp.*")

TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m is not None else ""


def formula(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return rdMolDescriptors.CalcMolFormula(m) if m is not None else ""


def skeleton(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    if m is None:
        return ""
    try:
        return Chem.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--probe", type=int, default=50, help="对多少个 miss 做两步可达性探测")
    ap.add_argument("--seed", type=int, default=20261014)
    ap.add_argument("--out", default=str(ROOT / "reports" / "miss_diag.jsonl"))
    a = ap.parse_args()

    import smartreact_engine as SE
    import templates as T
    from engine import Compound

    eng = SE.SmartReactEngine()
    cond = T.get_template("煎煮")
    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]
    random.Random(a.seed).shuffle(rows)

    t0 = time.time()
    n_eval = 0
    misses = []
    with open(a.out, "w", encoding="utf-8") as fo:
        for d in rows[: a.n]:
            rl = ast.literal_eval(d["reactants"]) if isinstance(d["reactants"], str) else d["reactants"]
            rl = [canon(s) for s in rl[:2]]
            rl = [s for s in rl if s]
            if not rl:
                continue
            want = canon(d.get("product") or "")
            if not want:
                continue
            comps = [Compound(smiles=s, name="R%d" % i, herb="(bench)")
                     for i, s in enumerate(rl)]
            try:
                prods = eng.step(comps, cond, round_no=1)
            except Exception:              # noqa: BLE001
                continue
            n_eval += 1
            cands = []
            for p in prods:
                cs = canon(getattr(p, "smiles", "") or "")
                if cs and cs not in cands:
                    cands.append(cs)
            if want in cands:
                continue
            rec = {
                "reactants": rl,
                "want": want,
                "want_formula": formula(want),
                "want_skel": skeleton(want),
                "n_cands": len(cands),
                "cands": cands[:12],
            }
            misses.append(rec)
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("评估 %d 条，miss %d 条（%.2f%%），%.1f s"
          % (n_eval, len(misses), 100.0 * len(misses) / max(1, n_eval), time.time() - t0))

    # —— 自动分类 ——
    skel_hit = form_hit = none = 0
    for m in misses:
        cs = m["cands"]
        m["skel_cands"] = sum(1 for c in cs if skeleton(c) == m["want_skel"])
        m["form_cands"] = sum(1 for c in cs if formula(c) == m["want_formula"])
        if m["skel_cands"]:
            skel_hit += 1
            m["cls"] = "技术性(立构/互变)"
        elif m["form_cands"]:
            form_hit += 1
            m["cls"] = "同分子式异构"
        else:
            none += 1
            m["cls"] = "待定(可能是真缺模板或需多步)"
    print("技术性(骨架相同) %d / 同分子式异构 %d / 待定 %d"
          % (skel_hit, form_hit, none))

    # —— 两步可达性（只对前 probe 条待定样本）——
    todo = [m for m in misses if m["cls"].startswith("待定")][: a.probe]
    reach2 = 0
    t1 = time.time()
    for m in todo:
        seeds = m["cands"][:5]
        hit = False
        for cs in seeds:
            try:
                prods = eng.step([Compound(smiles=cs, name="M", herb="(bench)")], cond, round_no=2)
            except Exception:          # noqa: BLE001
                continue
            if any(canon(getattr(p, "smiles", "") or "") == m["want"] for p in prods):
                hit = True
                break
        m["two_step"] = hit
        reach2 += 1 if hit else 0
    print("两步探测 %d 条（前 5 个候选各跑一轮）：可达 %d 条，%.1f s"
          % (len(todo), reach2, time.time() - t1))

    # —— 样例（给人看）——
    print("\n前 8 条待定 miss：")
    for m in [x for x in misses if x["cls"].startswith("待定")][:8]:
        r = " + ".join(x[:38] for x in m["reactants"])
        print("  %s\n    要: %s %s | 候选 %d 个，两步可达=%s"
              % (r, m["want_formula"], m["want"][:44], m["n_cands"], m.get("two_step", "未探测")))

    # 疑似缺模板的「最像」的几个反应类别：按 want 的环数分布给个粗看法
    rings = []
    for m in misses:
        mm = Chem.MolFromSmiles(m["want"])
        if mm is not None:
            rings.append(rdMolDescriptors.CalcNumRings(mm))
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_evaluated": n_eval,
        "n_miss": len(misses),
        "miss_rate": round(len(misses) / max(1, n_eval), 4),
        "classes": {
            "technical_stereo_or_tautomer": skel_hit,
            "same_formula_isomer": form_hit,
            "undecided": none,
        },
        "two_step_probe": {"n": len(todo), "reachable": reach2},
        "want_rings": {
            "mean": round(statistics.mean(rings), 2) if rings else None,
            "median": statistics.median(rings) if rings else None,
            "share_0ring": round(sum(1 for r in rings if r == 0) / max(1, len(rings)), 3),
        },
        "cand_median": statistics.median([m["n_cands"] for m in misses]) if misses else 0,
        "seconds": round(time.time() - t0, 1),
    }
    p = ROOT / "reports" / "miss_diag_20261104.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + json.dumps(out, ensure_ascii=False, indent=2))
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
