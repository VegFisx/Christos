# -*- coding: utf-8 -*-
"""Run the full leak-free engine (curated + mined_lf + base) on a holdout."""
import argparse
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

ROOT = Path(r"D:\ProgramData\DSHNS\chemreact-staging")
for _p in (ROOT / "core", ROOT / "tools", ROOT / "conditions", ROOT / "libs"):
    sys.path.insert(0, str(_p))

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

import templates as T
from engine import Compound
import smartreact_engine as SE

CASES = ROOT / "data" / "holdout_general_organic_295_20261123.json"
LF = ROOT / "reports" / "mined_forward_templates_full_lf.jsonl"
BASE = ROOT / "libs" / "smartreact" / "data" / "templates.txt"
OUT = ROOT / "reports" / "general_organic_full_lf295_20261123.json"


def canon(s):
    m = Chem.MolFromSmiles(s or "")
    return Chem.MolToSmiles(m) if m else ""


def key(s):
    m = Chem.MolFromSmiles(s or "")
    if m is None:
        return ""
    try:
        from rdkit.Chem import inchi
        return inchi.MolToInchiKey(m)[:14]
    except Exception:
        return ""


def load_support():
    sup = {}
    with LF.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("template") or ""
            if t:
                sup[t] = int(d.get("support") or 0)
    base_names, base_smarts = set(), set()
    with BASE.open(encoding="utf-8") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 5:
                base_names.add(p[0])
                if p[3]:
                    base_smarts.add(p[3])
    return sup, base_names, base_smarts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", default=str(CASES))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--extra-limit", type=int, default=20000)
    ap.add_argument("--mono-limit", type=int, default=6000)
    args = ap.parse_args()
    cases_path = Path(args.holdout)
    out_path = Path(args.out)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]
    sup, base_names, base_smarts = load_support()
    eng = SE.SmartReactEngine(
        use_curated_templates=True, allow_unvalidated=True,
        use_extra_templates=True, use_mono_templates=True,
        use_base_templates=True, rescue=False, stereo_enum_cap=0,
        strict_redox_gate=False, gate_conditions=False,
        extra_templates_path=str(LF), mono_templates_path=str(LF),
        extra_template_limit=int(args.extra_limit),
        mono_template_limit=int(args.mono_limit),
    )
    print("extra:", eng.extra_template_note)
    print("mono:", eng.mono_template_note)
    cond = T.get_template("煎煮")
    rows = []
    for i, c in enumerate(cases, 1):
        comps = [Compound(smiles=s, name="r%d" % (j + 1), herb="USPTO test")
                 for j, s in enumerate(c["reactants"])]
        t0 = time.time()
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception as ex:
            rows.append({"id": c["id"], "class": c["class"],
                         "error": "%s: %s" % (type(ex).__name__, ex)})
            print("ERR", c["id"], ex, flush=True)
            continue
        want = key(c["product"])
        exact_want = canon(c["product"])
        hits = [p for p in prods if want and key(getattr(p, "smiles", "")) == want]
        sources, rules, supports = set(), set(), []
        for p in hits:
            tm = str(getattr(p, "template_smarts", "") or "")
            rid = str(getattr(p, "rule_id", "") or "")
            rules.add(rid)
            if tm and tm in sup:
                sources.add("mined_lf")
                supports.append(sup[tm])
            elif tm and tm in base_smarts:
                sources.add("base")
            elif rid in base_names:
                sources.add("base")
            elif rid:
                sources.add("curated")
            else:
                sources.add("other")
        rows.append({
            "id": c["id"], "class": c["class"],
            "hit": bool(hits), "n_products": len(prods),
            "exact": any(canon(getattr(p, "smiles", "")) == exact_want for p in hits),
            "sources": sorted(sources), "hit_rules": sorted(rules),
            "mined_supports": sorted(supports),
            "seconds": round(time.time() - t0, 2),
        })
        print(" %2d/%2d %-42s %s %s p=%d"
              % (i, len(cases), c["id"], "HIT" if hits else ".",
                 sorted(sources), len(prods)), flush=True)

    ok = [r for r in rows if r.get("hit")]
    src_cases = Counter(s for r in ok for s in r.get("sources", []))
    supports = sorted(x for r in ok for x in r.get("mined_supports", []))
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": "curated(all)+extra/mono=full_lf+base; no rescue/stereo; gate_conditions=False",
        "n": len(cases), "hits": len(ok),
        "exact": sum(bool(r.get("exact")) for r in ok),
        "errors": sum("error" in r for r in rows),
        "cases_with_source": dict(src_cases),
        "mined_support": {
            "n": len(supports),
            "min": supports[0] if supports else None,
            "p10": supports[len(supports) // 10] if supports else None,
            "median": supports[len(supports) // 2] if supports else None,
            "max": supports[-1] if supports else None,
        },
        "rows": rows,
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsummary", json.dumps({k: v for k, v in out.items() if k != "rows"},
                                  ensure_ascii=False, indent=1))
    print("written", out_path)


if __name__ == "__main__":
    main()
