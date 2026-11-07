#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A1 追问：这 10 条 miss 到底是「没模板」还是「产物对不上字符串」。

对每条 miss 问四件事（全部实测）：
  Q1 有没有模板能在这对反应物上**出任何产物**（fires_any）
  Q2 出的产物里，有没有一条**等于目标**（严格）
  Q3 有没有一条**立体无关地等于目标**（去手性后比）
  Q4 若有 Q3 命中，那条产物的立体信息与目标差在哪

用法：python -I tools\\diag_a1_strings.py [--n 8]
"""
from __future__ import annotations

import argparse
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


def smi(m, iso=True) -> str:
    if m is None:
        return ""
    try:
        return Chem.MolToSmiles(m, isomericSmiles=iso)
    except Exception:  # noqa: BLE001
        return ""


def flat(s: str) -> str:
    return smi(Chem.MolFromSmiles(s), iso=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    a = ap.parse_args()

    rows = [json.loads(l) for l in (ROOT / "reports" / "miss_diag.jsonl").open(encoding="utf-8")]
    t0 = time.time()
    tpls = L.load_mined_templates(TPL, min_support=1, limit=None)
    print("模板 %d 条（%.1fs）" % (len(tpls), time.time() - t0))

    out = []
    for row in rows[: a.n]:
        want = row.get("want") or ""
        want_flat = flat(want)
        subs = [Chem.MolFromSmiles(s) for s in (row.get("reactants") or [])]
        subs = [m for m in subs if m is not None]
        rec = {"want": want, "reactants": row.get("reactants"),
               "fires_any": 0, "strict": 0, "flat": 0, "stereo_diffs": []}
        for t in tpls:
            smarts = t.get("smarts") if isinstance(t, dict) else getattr(t, "smarts", "")
            if not smarts or ">>" not in smarts:
                continue
            try:
                rxn = AllChem.ReactionFromSmarts(smarts)
            except Exception:  # noqa: BLE001
                continue
            if rxn is None or rxn.GetNumReactantTemplates() != 2 or len(subs) != 2:
                continue
            for pair in ((subs[0], subs[1]), (subs[1], subs[0])):
                try:
                    prods = rxn.RunReactants(pair)
                except Exception:  # noqa: BLE001
                    continue
                for p in prods:
                    s = smi(p[0])
                    if not s:
                        continue
                    rec["fires_any"] += 1
                    if s == want:
                        rec["strict"] += 1
                    elif flat(s) == want_flat:
                        rec["flat"] += 1
                        if len(rec["stereo_diffs"]) < 3:
                            rec["stereo_diffs"].append(s)
                if rec["strict"] or rec["flat"]:
                    break
            if rec["strict"] or rec["flat"]:
                break
        out.append(rec)
        print("  fires_any=%-4d strict=%-2d flat=%-2d  %s" %
              (rec["fires_any"], rec["strict"], rec["flat"], want[:44]))

    p = ROOT / "reports" / "a1_strings_diag.json"
    p.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                             "rows": out}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n写出 %s（%.1fs）" % (p, time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
