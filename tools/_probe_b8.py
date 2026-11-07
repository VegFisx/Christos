# -*- coding: utf-8 -*-
# B8 探索（一次性）：从 50k 逐切断数据里找"高产出、极低可用"的未拉黑模板（R2 家族等）
import json
import sys
from collections import Counter
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

from rdkit import Chem, RDLogger                        # noqa: E402
from rdkit.Chem import rdChemReactions                  # noqa: E402
RDLogger.DisableLog("rdApp.*")

LIB = STAGE / "reports" / "paper" / "data" / "lib_uspto50k_excl.jsonl"
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

rows = [json.loads(l) for l in open(STAGE / "reports" / "paper" / "results"
                                    / "usability_per_cut.jsonl", encoding="utf-8")
        if l.strip()]
bl = json.loads((STAGE / "reports" / "retro_template_blacklist.json")
                .read_text(encoding="utf-8"))
blset = {str(e.get("smarts")) for e in bl.get("entries", [])} | \
        {str(e.get("smarts")) for e in bl.get("noop_entries", [])}

agg = {}
for r in rows:
    t = r["t"]
    a = agg.setdefault(t, {"n": 0, "usable": 0, "r2": 0})
    a["n"] += 1
    if r["ok"]:
        a["usable"] += 1
    if str(r["why"]).startswith("R2"):
        a["r2"] += 1

cands = []
for t, a in agg.items():
    sm = lib[t]["smarts"] if 0 <= t < len(lib) else "?"
    if sm in blset or a["n"] < 500:
        continue
    cands.append({"t": t, "smarts": sm, "freq": lib[t]["freq"] if t < len(lib) else 0,
                  "n_cuts": a["n"], "n_usable": a["usable"], "n_R2": a["r2"]})
cands.sort(key=lambda x: -x["n_cuts"])
print("未拉黑、样本内切断≥500 的模板 %d 条（按切断量排序，前 25）：" % len(cands))
for c in cands[:25]:
    print("   cuts %6d · R2 %6d · usable %5d (%.2f%%) · freq %-3s · %s"
          % (c["n_cuts"], c["n_R2"], c["n_usable"],
             100.0 * c["n_usable"] / max(1, c["n_cuts"]), c["freq"], c["smarts"][:76]))

strict = [c for c in cands if c["n_cuts"] >= 1000 and c["n_usable"] <= 2]
print()
print("候选规则（切断>=1000 且 可用<=2）命中 %d 条 · 合计切断 %d · 可用 %d"
      % (len(strict), sum(c["n_cuts"] for c in strict),
         sum(c["n_usable"] for c in strict)))
for c in strict[:30]:
    print("   [%4d] %s" % (c["t"], c["smarts"][:96]))
