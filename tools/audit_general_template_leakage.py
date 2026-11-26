# -*- coding: utf-8 -*-
"""审计 30 条外部反应上 full engine 的模板来源与泄漏风险。

检查：
  1. base templates.txt 的 example 反应是否与 30 条样本 exact/同底物重叠；
  2. 每个命中产物来自 base / mined(ORD) / curated；
  3. mined 命中模板的 ORD support 分布（低 support 更接近记忆）；
  4. mined 文件的 src 分布。

用法：
    python tools\\audit_general_template_leakage.py
输出：reports/template_audit_general30_20261123.json
"""
from __future__ import annotations

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

from rdkit import Chem, RDLogger
RDLogger.DisableLog("rdApp.*")

import templates as T
from engine import Compound
import smartreact_engine as SE

CASES = ROOT / "data" / "holdout_general_organic_20261123.json"
BASE = ROOT / "libs" / "smartreact" / "data" / "templates.txt"
MINED = ROOT / "reports" / "mined_forward_templates_full_s5.jsonl"
OUT = ROOT / "reports" / "template_audit_general30_20261123.json"


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


def load_base():
    exact, substrates, base_names, base_smarts = set(), set(), set(), set()
    n = 0
    with BASE.open(encoding="utf-8") as f:
        f.readline()
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 5:
                continue
            name, _tid, example, smarts = p[0], p[1], p[2], p[3]
            base_names.add(name)
            if smarts:
                base_smarts.add(smarts)
            if ">>" not in example:
                continue
            lhs, rhs = example.split(">>", 1)
            subs = [canon(x) for x in lhs.split(".") if x]
            prods = [canon(x) for x in rhs.split(".") if x]
            if not subs or not prods or any(not x for x in subs + prods):
                continue
            n += 1
            exact.add((frozenset(subs), prods[0]))
            substrates.add(frozenset(subs))
    return exact, substrates, base_names, base_smarts, n


def load_mined():
    support, src = {}, Counter()
    with MINED.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            t = d.get("template") or ""
            if t:
                support[t] = int(d.get("support") or 0)
            src[str(d.get("src") or "")] += 1
    return support, src


def main():
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    exact, substrates, base_names, base_smarts, n_base_examples = load_base()
    mined_support, mined_src = load_mined()

    eng = SE.SmartReactEngine(
        use_curated_templates=True, allow_unvalidated=True,
        use_extra_templates=True, use_mono_templates=True,
        use_base_templates=True, rescue=False, stereo_enum_cap=0,
        strict_redox_gate=False, gate_conditions=False,
    )
    cond = T.get_template("煎煮")

    rows = []
    for i, c in enumerate(cases, 1):
        subs = [canon(s) for s in c["reactants"]]
        target = canon(c["product"])
        target_key = key(target)
        comps = [Compound(smiles=s, name="r%d" % (j + 1), herb="USPTO test")
                 for j, s in enumerate(subs)]
        try:
            prods = eng.step(comps, cond, round_no=1)
        except Exception as ex:
            rows.append({"id": c["id"], "class": c["class"],
                         "error": "%s: %s" % (type(ex).__name__, ex)})
            print("ERR", c["id"], ex, flush=True)
            continue
        hits = [p for p in prods
                if target_key and key(getattr(p, "smiles", "")) == target_key]
        sources = set()
        hit_rules = set()
        mined_supports = []
        for p in hits:
            tm = str(getattr(p, "template_smarts", "") or "")
            rid = str(getattr(p, "rule_id", "") or "")
            hit_rules.add(rid)
            if tm and tm in mined_support:
                sources.add("mined_ord")
                mined_supports.append(mined_support[tm])
            elif tm and tm in base_smarts:
                sources.add("base_smarts")
            elif rid in base_names:
                sources.add("base_rule")
            elif rid:
                sources.add("curated")
            else:
                sources.add("other")
        subs_key = frozenset(subs)
        rows.append({
            "id": c["id"], "class": c["class"],
            "hit": bool(hits),
            "n_hit_products": len(hits),
            "hit_rules": sorted(hit_rules),
            "hit_sources": sorted(sources),
            "mined_supports": sorted(mined_supports),
            "base_exact_overlap": (subs_key, target) in exact,
            "base_substrate_overlap": subs_key in substrates,
        })
        print(" %2d/%2d %-42s hit=%s sources=%s support=%s"
              % (i, len(cases), c["id"], bool(hits), sorted(sources),
                 sorted(mined_supports)[:5]), flush=True)

    ok = [r for r in rows if r.get("hit")]
    src_cases = Counter(s for r in ok for s in r.get("hit_sources", []))
    sup = sorted(x for r in ok for x in r.get("mined_supports", []))
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_cases": len(cases),
        "n_hits": len(ok),
        "n_errors": sum("error" in r for r in rows),
        "base": {
            "n_examples": n_base_examples,
            "exact_overlap_cases": sum(bool(r.get("base_exact_overlap")) for r in rows),
            "same_substrates_cases": sum(bool(r.get("base_substrate_overlap")) for r in rows),
        },
        "mined": {
            "n_templates": len(mined_support),
            "src": dict(mined_src),
            "support_min": sup[0] if sup else None,
            "support_p10": sup[len(sup) // 10] if sup else None,
            "support_median": sup[len(sup) // 2] if sup else None,
            "support_max": sup[-1] if sup else None,
            "n_hits_with_mined": len(sup),
            "share_support_le10": (sum(x <= 10 for x in sup) / len(sup)) if sup else None,
        },
        "cases_with_source": dict(src_cases),
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsummary", json.dumps({k: v for k, v in out.items() if k != "rows"},
                                  ensure_ascii=False, indent=1))
    print("written", OUT)


if __name__ == "__main__":
    main()
