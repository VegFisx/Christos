# -*- coding: utf-8 -*-
r"""给切断打**行为标签**：ORD 里有没有"同一产物 + 同一反应物集合"的真实记录。

用法（索引建好之后；Miniconda 或 venv 都能跑）：

    python tools\label_cuts_with_precedent.py --cuts annotation   # 72 条盲标
    python tools\label_cuts_with_precedent.py --cuts audit        # 3,320 条审计切断

判定（三档，可判定）：
  * **有先例**：ORD 里存在同一产物、且反应物集合完全相同的记录；
  * **部分先例**：产物相同，但反应物集合是其子集/超集（同一底物家族，条件更可能适用）；
  * **无先例**：ORD 里找不到同一产物的记录。

产出：`data\cut_precedent_labels.json` + 打印一致率（与我们 R1–R4 判据对照）。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
IDX = STAGE / "data" / "ord_reaction_index.jsonl"
ANN = STAGE / "reports" / "paper" / "results" / "annotation_candidates.jsonl"
AUDIT = STAGE / "reports" / "_dirty8_r1_pairs.jsonl"
USAB = STAGE / "reports" / "paper" / "results" / "usability_per_cut.jsonl"
OUT = STAGE / "data" / "cut_precedent_labels.json"

sys.path.insert(0, str(STAGE / "libs"))
sys.path.insert(0, str(STAGE / "core"))
from rdkit import Chem, RDLogger                          # noqa: E402
RDLogger.DisableLog("rdApp.*")


def canon(s: str) -> str:
    m = Chem.MolFromSmiles(s) if s else None
    return Chem.MolToSmiles(m) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", default="annotation", choices=("annotation", "audit"))
    a = ap.parse_args()
    if not IDX.exists():
        print("★ 缺索引：先跑 tools\\build_ord_reaction_index.py（venv 3.12）")
        return 1
    # 1) 建 产物 → [反应物集合] 索引
    by_prod = defaultdict(list)
    n_idx = 0
    for ln in IDX.open(encoding="utf-8"):
        try:
            d = json.loads(ln)
        except Exception:                                    # noqa: BLE001
            continue
        n_idx += 1
        for p in d.get("products") or []:
            by_prod[p].append((tuple(d.get("reactants") or []), d.get("rid"),
                               d.get("catalysts"), d.get("temp")))
    print("索引：%d 条反应，涉及产物 %d 个" % (n_idx, len(by_prod)))
    # 2) 读切断
    if a.cuts == "annotation":
        rows = [json.loads(l) for l in ANN.open(encoding="utf-8") if l.strip()]
        items = [{"i": r["i"], "target": r["target"], "precursors": r["precursors"]}
                 for r in rows]
    else:
        rows = [json.loads(l) for l in AUDIT.open(encoding="utf-8") if l.strip()]
        items = [{"i": r.get("idx"), "target": r["target"], "precursors": r["precursors"]}
                 for r in rows]
        # 系统判据（可选对照）
        sysv = {}
        if USAB.exists():
            for ln in USAB.open(encoding="utf-8"):
                try:
                    d = json.loads(ln)
                except Exception:                            # noqa: BLE001
                    continue
                sysv[str(d.get("i"))] = d.get("why")
    # 3) 打标
    out, stat = {}, {"有先例": 0, "部分先例": 0, "无先例": 0}
    for it in items:
        pt = canon(it["target"])
        ps = {canon(x) for x in (it["precursors"] or []) if canon(x)}
        hits = by_prod.get(pt) or []
        best, tag = None, "无先例"
        for rs, rid, cats, temp in hits:
            rss = set(rs)
            if rss == ps:
                tag, best = "有先例", {"rid": rid, "catalysts": cats[:3], "temp": temp}
                break
            if ps and (ps <= rss or rss <= ps):
                tag, best = "部分先例", {"rid": rid, "catalysts": cats[:3], "temp": temp}
        stat[tag] += 1
        rec = {"target": it["target"], "precursors": it["precursors"], "label": tag}
        if best:
            rec.update(best)
        out[str(it["i"])] = rec
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(items)
    print("切断 %d 条：" % n)
    for k, v in stat.items():
        print("  %-6s %5d（%.1f%%）" % (k, v, 100.0 * v / max(1, n)))
    # 4) 与系统判据对照（仅 audit 集有 why）
    if a.cuts == "audit" and 'sysv' in dir():
        tab = defaultdict(int)
        for i, rec in out.items():
            w = sysv.get(str(i)) or "?"
            tab[(w, rec["label"])] += 1
        print()
        print("系统判据 × 行为标签（前 12 行）：")
        for (w, lb), c in sorted(tab.items(), key=lambda x: -x[1])[:12]:
            print("   %-22s × %-6s %5d" % (w, lb, c))
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
