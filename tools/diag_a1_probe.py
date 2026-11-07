#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A1 可行性探针：给「缺产物」补一个试剂分子，能不能真的把目标产物生出来？

口径（三条，全部实测，不假设）：
  1. 候选模板 = 41,619 条 mined 模板里，**产物侧片段全部能在目标产物里找到**的那些
     （产物侧只写变化片段，未映射原子由反应物保留 —— 第 99 轮已确认，方向不能反）。
  2. 「补试剂」的分子**不手写**：直接把模板自己的第二个反应物 SMARTS 实例化成一个
     具体分子（`MolFromSmarts` → `MolToSmiles`），因此补出来的试剂永远与模板同源。
  3. 判成功 = `RunReactants` 真的产出 canonical SMILES 等于目标产物。

用法：
    python -I tools\\diag_a1_probe.py [--n 12] [--min-support 100]
"""
from __future__ import annotations

import argparse
import collections
import json
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
from rdkit.Chem import AllChem  # noqa: E402

RDLogger.DisableLog("rdApp.*")

import rdkit_template_lib as L  # noqa: E402

TPL = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"


def canon(m) -> str:
    if m is None:
        return ""
    try:
        return Chem.MolToSmiles(m)
    except Exception:  # noqa: BLE001
        return ""


def fragments_of(product_side: str) -> list:
    out = []
    for part in product_side.split("."):
        if not part.strip():
            continue
        m = Chem.MolFromSmarts(part)
        if m is not None and m.GetNumAtoms():
            out.append(m)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--min-support", type=int, default=100)
    a = ap.parse_args()

    rows = [json.loads(l) for l in (ROOT / "reports" / "miss_diag.jsonl").open(encoding="utf-8")]
    t0 = time.time()
    tpls = L.load_mined_templates(TPL, min_support=a.min_support, limit=None)
    print("载入 mined 模板 %d 条（support>=%d，%.1fs）" % (len(tpls), a.min_support, time.time() - t0))

    stat = collections.Counter()
    recovered = []
    for row in rows[: a.n]:
        want = row.get("want") or ""
        wmol = Chem.MolFromSmiles(want)
        subs = [Chem.MolFromSmiles(s) for s in (row.get("reactants") or [])]
        subs = [m for m in subs if m is not None]
        if wmol is None or not subs:
            stat["bad"] += 1
            continue

        # 1) 候选：产物侧片段全部在目标里
        cands = []
        for t in tpls:
            smarts = t.get("smarts") if isinstance(t, dict) else getattr(t, "smarts", "")
            if not smarts or ">>" not in smarts:
                continue
            left, right = smarts.split(">>", 1)
            frags = fragments_of(right)
            if frags and all(wmol.HasSubstructMatch(f) for f in frags):
                cands.append((t, smarts, left))
        stat["cand_templates"] += len(cands)
        if not cands:
            stat["no_cand"] += 1
            continue

        # 2) 先看原配对能不能出目标，再试「补试剂」
        got_with_pair = False
        got_with_reagent = False
        for _t, smarts, left in cands[:400]:
            rxn = None
            try:
                rxn = AllChem.ReactionFromSmarts(smarts)
            except Exception:  # noqa: BLE001
                continue
            if rxn is None:
                continue
            # 原配对
            try:
                if rxn.GetNumReactantTemplates() == 2 and len(subs) == 2:
                    for order in ((0, 1), (1, 0)):
                        prods = rxn.RunReactants((subs[order[0]], subs[order[1]]))
                        for p in prods:
                            if canon(p[0]) == want:
                                got_with_pair = True
                                break
                        if got_with_pair:
                            break
            except Exception:  # noqa: BLE001
                pass
            if got_with_pair:
                break
            # 补试剂：把模板缺的那一侧 SMARTS 实例化
            try:
                parts = [x for x in left.split(".") if x.strip()]
            except Exception:  # noqa: BLE001
                parts = []
            if len(parts) == 2 and len(subs) == 1:
                raw = Chem.MolFromSmarts(parts[1])
                if raw is None:
                    continue
                inst = Chem.MolFromSmiles(canon(raw) or "", sanitize=False)
                if inst is None:
                    continue
                try:
                    Chem.SanitizeMol(inst, catchErrors=True)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    for order in ((0, 1), (1, 0)):
                        pair = (subs[0], inst) if order[0] == 0 else (inst, subs[0])
                        prods = rxn.RunReactants(pair)
                        for p in prods:
                            if canon(p[0]) == want:
                                got_with_reagent = True
                                break
                        if got_with_reagent:
                            break
                except Exception:  # noqa: BLE001
                    pass
            if got_with_reagent:
                break

        if got_with_pair:
            stat["ok_pair"] += 1
        elif got_with_reagent:
            stat["ok_reagent"] += 1
            recovered.append({"want": want, "reactants": row.get("reactants")})
        else:
            stat["still_miss"] += 1

    print("\n探针 %d 条（%.1fs）：" % (a.n, time.time() - t0))
    for k in ("ok_pair", "ok_reagent", "still_miss", "no_cand", "bad"):
        if stat[k]:
            print("  %-12s %d" % (k, stat[k]))
    print("  候选模板累计 %d 条" % stat["cand_templates"])
    if recovered:
        print("\n补试剂后成功：")
        for r in recovered[:5]:
            print("  %s  <=  %s" % (r["want"][:60], r["reactants"]))

    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "n": a.n,
           "min_support": a.min_support, "stat": dict(stat), "recovered": recovered}
    p = ROOT / "reports" / "a1_probe.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
