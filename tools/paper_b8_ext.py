# -*- coding: utf-8 -*-
r"""B8（2026-10-14）：第二批黑名单候选 —— "保护基/官能化添加"逆用族（R2 家族）。

判据（写死，全部来自既有实测数据）：
  * 数据源：reports/paper/results/usability_per_cut.jsonl（USPTO-50k 抽样 2,930 产物、
    496,047 个切断；与生产判据同一函数）
  * 入选：样本内切断 ≥ 1000 · 可用 ≤ 2 · **全部切断都是 R2（结构上必然是"前体更大"）**
  * 输出：reports/paper/results/blacklist_ext_r2.json（含每条证据：切断/可用/R2/freq，
    并与生产库 retro_templates_clustered.jsonl 核对 smarts 是否存在）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (STAGE / "libs", STAGE / "tools"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from rdkit.Chem import rdChemReactions              # noqa: E402
from rdkit import RDLogger                          # noqa: E402
RDLogger.DisableLog("rdApp.*")

RES = STAGE / "reports" / "paper" / "results"
LIB = STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl.jsonl"
PROD_LIB = STAGE / "reports" / "retro_templates_clustered.jsonl"
OUT = RES / "blacklist_ext_r2.json"
MIN_CUTS, MAX_USABLE = 1000, 2


def main() -> int:
    lib = []
    for line in open(LIB, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        try:
            rx = rdChemReactions.ReactionFromSmarts(r["template"])
        except Exception:
            rx = None
        if rx is None or rx.GetNumReactantTemplates() != 1:
            continue
        lib.append({"smarts": r["template"], "freq": int(r.get("freq") or 0)})

    rows = [json.loads(l) for l in open(RES / "usability_per_cut.jsonl",
                                        encoding="utf-8") if l.strip()]
    bl = json.loads((STAGE / "reports" / "retro_template_blacklist.json")
                    .read_text(encoding="utf-8"))
    already = {str(e.get("smarts")) for e in bl.get("entries", [])} | \
              {str(e.get("smarts")) for e in bl.get("noop_entries", [])}

    agg = {}
    for r in rows:
        a = agg.setdefault(r["t"], {"n": 0, "usable": 0, "r2": 0})
        a["n"] += 1
        if r["ok"]:
            a["usable"] += 1
        if str(r["why"]).startswith("R2"):
            a["r2"] += 1

    entries = []
    skip_not_all_r2 = 0
    for t, a in sorted(agg.items()):
        sm = lib[t]["smarts"] if 0 <= t < len(lib) else ""
        if not sm or sm in already:
            continue
        if a["n"] >= MIN_CUTS and a["usable"] <= MAX_USABLE:
            if a["r2"] != a["n"]:                 # 要求"结构上必然放大"
                skip_not_all_r2 += 1
                continue
            entries.append({"smarts": sm, "freq_bench": lib[t]["freq"],
                            "n_cuts": a["n"], "n_usable": a["usable"], "n_R2": a["r2"]})

    prod = {json.loads(l)["template"] for l in open(PROD_LIB, encoding="utf-8")
            if l.strip()}
    for e in entries:
        e["in_prod_lib"] = e["smarts"] in prod
    n_prod = sum(1 for e in entries if e["in_prod_lib"])

    out = {
        "generated": "2026-10-14",
        "criterion": ("样本内切断>=%d 且 可用<=%d 且 全部切断为 R2（结构上必然放大）；"
                      "数据=usability_per_cut.jsonl（50k 抽样 2,930 产物）" % (MIN_CUTS, MAX_USABLE)),
        "n_entries": len(entries),
        "totals": {"n_cuts": sum(e["n_cuts"] for e in entries),
                   "n_usable": sum(e["n_usable"] for e in entries),
                   "n_R2": sum(e["n_R2"] for e in entries)},
        "n_in_prod_lib": n_prod, "n_not_in_prod_lib": len(entries) - n_prod,
        "skip_not_all_r2": skip_not_all_r2,
        "entries": entries,
    }
    RES.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("B8 扩展候选：%d 条（全部 R2；合计切断 %d · 可用 %d）"
          % (len(entries), out["totals"]["n_cuts"], out["totals"]["n_usable"]))
    print("  在生产库(3,228)中存在：%d 条（缺 %d）" % (n_prod, len(entries) - n_prod))
    print("  因'不是全 R2'被跳过：%d 条" % skip_not_all_r2)
    for e in entries[:8]:
        print("   [%5d cuts] %s" % (e["n_cuts"], e["smarts"][:90]))
    print("写出：%s" % OUT.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
