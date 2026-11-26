# -*- coding: utf-8 -*-
"""Classify dev misses by mapped bond changes (C-N, C-O, C-C, ...).

Uses RXNMapper + mapped_chem.  Dev is allowed for gap analysis; blind1 is not
touched here.
"""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "libs", ROOT / "tools"):
    sys.path.insert(0, str(p))
from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")
import mapped_chem as mc
from rxnmapper import RXNMapper

CASES = json.loads((ROOT / "data" / "dev_general_organic_20261124.json").read_text(encoding="utf-8"))["cases"]
RES = json.loads((ROOT / "reports" / "general_organic_full_lf_dev_20261124.json").read_text(encoding="utf-8"))["rows"]
MISS = {r["id"] for r in RES if not r.get("hit")}
rows = [c for c in CASES if c["id"] in MISS]

mapper = RXNMapper()
classes = Counter()
examples = defaultdict(list)
failed = []
for c in rows:
    rxn = ".".join(c["reactants"]) + ">>" + c["product"]
    try:
        mr = mapper.get_attention_guided_atom_maps([rxn])[0].get("mapped_rxn") or ""
        lhs, rhs = mr.split(">>", 1)
        prod = mc.parse_mapped(rhs, context=c["id"])
        if prod is None or not mc.map_nums(prod):
            raise ValueError("no product maps")
        raws, _plains = mc.contributing_components(lhs, mc.map_nums(prod))
        left = mc.bonds_over_maps_all(raws)
        formed, broken = mc.formed_broken(prod, left)
        elem = {}
        for m in [prod] + [mc.parse_mapped(x) for x in raws]:
            if m is None:
                continue
            for a in m.GetAtoms():
                if a.GetAtomMapNum():
                    elem[a.GetAtomMapNum()] = a.GetSymbol()
        def sig(bonds, prefix):
            out = []
            for a, b in bonds:
                ea, eb = elem.get(a, "?"), elem.get(b, "?")
                if "?" in (ea, eb):
                    continue
                out.append("%s-%s" % tuple(sorted((ea, eb))))
            return [prefix + x for x in sorted(set(out))]
        s = tuple(sorted(sig(formed, "f:") + sig(broken, "b:")))
        key = "|".join(s) if s else "(no mapped bond change)"
        classes[key] += 1
        if len(examples[key]) < 3:
            examples[key].append((c["id"], c["reactants"], c["product"]))
    except Exception as ex:
        failed.append((c["id"], "%s: %s" % (type(ex).__name__, ex)))

print("dev misses", len(rows), "mapped", len(rows) - len(failed), "failed", len(failed))
print("\nTOP CLASSES")
for k, n in classes.most_common(25):
    print("\n", n, k)
    for cid, rs, p in examples[k][:1]:
        print("  ", cid, "R", " | ".join(rs)[:220])
        print("      P", p[:220])

out = {
    "n_misses": len(rows),
    "n_mapped": len(rows) - len(failed),
    "failed": failed,
    "classes": [{"signature": k, "n": n, "examples": examples[k]}
                for k, n in classes.most_common()],
}
(ROOT / "reports" / "dev_reaction_classes_20261124.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwritten reports/dev_reaction_classes_20261124.json")
