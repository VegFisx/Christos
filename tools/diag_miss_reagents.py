#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""缺产物 miss 的「反应物类型」归因：有多少 miss 是因为反应物里带金属试剂/保护基。

动机：`tools/diag_misses.py` 捞出 226 条 miss，人工看样例时发现很多带 Mg+/Si/Boc，
怀疑引擎根本不建模「试剂介导」的转化。这里只做计数，不做判断。

用法：
    python -I tools\\diag_miss_reagents.py
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
TESTSET = ROOT / "reports" / "paper" / "data" / "uspto50k_canon.jsonl"
MISS = ROOT / "reports" / "miss_diag.jsonl"

METAL = ("[Mg", "[Li", "[Zn", "[Na", "[K", "[Cu", "[Si", "[B", "[Sn", "[Al", "[Fe", "[Pd", "[Ni")
BOC = ("OC(=O)OC(=O)OC(C)(C)C", "OC(C)(C)C", "OCc1ccccc1", "OCc2ccccc2", "C(=O)OCc")


def kind(smiles_list):
    joined = " ".join(smiles_list)
    has_metal = any(t in joined for t in METAL)
    has_charge = "+]" in joined or "-]" in joined
    has_boc = any(t in joined for t in BOC)
    if has_metal or has_charge:
        return "金属/离子试剂"
    if has_boc:
        return "保护基/大位阻基"
    return "普通共价反应物"


def main() -> int:
    misses = [json.loads(l) for l in MISS.open(encoding="utf-8")]
    rows = [json.loads(l) for l in TESTSET.open(encoding="utf-8")]

    def canon_pairs(d):
        rl = ast.literal_eval(d["reactants"]) if isinstance(d["reactants"], str) else d["reactants"]
        return [str(s) for s in rl[:2]]

    m_cnt, b_cnt = {}, {}
    for m in misses:
        k = kind(m["reactants"])
        m_cnt[k] = m_cnt.get(k, 0) + 1
    for d in rows:
        k = kind(canon_pairs(d))
        b_cnt[k] = b_cnt.get(k, 0) + 1

    nm, nb = max(1, len(misses)), max(1, len(rows))
    print("miss 归因（%d 条）：" % len(misses))
    for k in sorted(m_cnt, key=lambda x: -m_cnt[x]):
        print("  %-18s %4d 条  %5.1f%%（全库占比 %.1f%%）"
              % (k, m_cnt[k], 100.0 * m_cnt[k] / nm, 100.0 * b_cnt.get(k, 0) / nb))
    out = {
        "n_miss": len(misses),
        "n_all": len(rows),
        "miss_by_kind": {k: {"n": v, "share": round(100.0 * v / nm, 2)} for k, v in m_cnt.items()},
        "all_by_kind": {k: {"n": v, "share": round(100.0 * v / nb, 2)} for k, v in b_cnt.items()},
    }
    p = ROOT / "reports" / "miss_reagent_breakdown.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("写出 %s" % p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
