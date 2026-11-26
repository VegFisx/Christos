# -*- coding: utf-8 -*-
r"""Link each active unvalidated rule to ORD mined templates (support evidence).

Three match levels, from strong to weak:
  exact   normalized SMARTS string equal (either orientation)
  skel    same atom-map skeleton after stripping atom-property queries
          ([C;D1;H3:1] -> [C:1]), either orientation
  weak    one normalized SMARTS contains the other's reaction center (substring)

The result says "this transformation class exists in ORD with support N".
It does NOT say "this exact rule was executed N times" -- applying rules to
the 900k ORD rows is a separate, expensive job.

Never edits rules/rules.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
MINE = ROOT / "reports" / "mined_forward_templates_full_lf.jsonl"
OUT_JSON = ROOT / "reports" / "rule_evidence_20261124.json"
OUT_MD = ROOT / "reports" / "rule_evidence_20261124.md"

ATOM = re.compile(r"\[([^\]]*):(\d+)\]")
LIT = re.compile(r"(JACS|J\.?\s*Am\.?\s*Chem\.?\s*Soc|Angew|Org\.?\s*Lett|"
                 r"J\.?\s*Org\.?\s*Chem|Tetrahedron|Chem\.?\s*Rev|Nature|Science|"
                 r"IJMS|Molecules|Phytochemistry|J\.?\s*Ethnopharmacol)"
                 r"[^0-9]{0,20}(\d{4})", re.I)
DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s or ""))


def skel(s: str) -> str:
    def repl(m):
        body, mnum = m.group(1), m.group(2)
        z = re.match(r"#(\d+)", body)
        if z:
            return "[#%s:%s]" % (z.group(1), mnum)
        el = re.match(r"([A-Za-z][a-z]?)", body)
        if el:
            sym = el.group(1)
            if sym.islower() or (len(sym) == 1 and sym.islower()):
                return "[%s:%s]" % (sym, mnum)
            return "[%s:%s]" % (sym, mnum)
        return m.group(0)
    return ATOM.sub(repl, norm(s))


def either(a: str, b: str) -> bool:
    if a == b:
        return True
    if ">>" not in a or ">>" not in b:
        return False
    al, ar = a.split(">>", 1)
    bl, br = b.split(">>", 1)
    return al == br and ar == bl


def main() -> int:
    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = [r for r in d["rules"]
             if str(r.get("status") or "active") == "active"
             and str(r.get("provenance") or "unvalidated") == "unvalidated"]

    mined = []
    with MINE.open(encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            x = json.loads(ln)
            t = x.get("template") or ""
            if not t:
                continue
            mined.append({"t": norm(t), "sk": skel(t),
                          "support": int(x.get("support") or 0),
                          "src": x.get("src") or ""})
    print("mined templates", len(mined))

    rows = []
    for r in rules:
        rt = norm(r.get("smarts") or "")
        rsk = skel(rt)
        best = {"level": "none", "support": 0, "template": ""}
        n_exact = n_skel = n_weak = 0
        for m in mined:
            if either(rt, m["t"]):
                n_exact += 1
                if m["support"] > best["support"]:
                    best = {"level": "exact", "support": m["support"],
                            "template": m["t"]}
                continue
            if either(rsk, m["sk"]):
                n_skel += 1
                if best["level"] != "exact" and m["support"] > best["support"]:
                    best = {"level": "skel", "support": m["support"],
                            "template": m["t"]}
                continue
            if len(rt) >= 20 and (rt in m["t"] or m["t"] in rt):
                n_weak += 1
                if best["level"] == "none" and m["support"] > best["support"]:
                    best = {"level": "weak", "support": m["support"],
                            "template": m["t"]}
        notes = r.get("notes") or ""
        lit = LIT.search(notes)
        doi = DOI.search(notes)
        rows.append({
            "id": r["id"], "category": r.get("category"),
            "n_exact": n_exact, "n_skel": n_skel, "n_weak": n_weak,
            "best_level": best["level"], "best_support": best["support"],
            "best_template": best["template"],
            "literature_hint": ("%s %s" % (lit.group(1), lit.group(2))) if lit else "",
            "doi_in_notes": doi.group(0) if doi else "",
        })

    def rank(x):
        lvl = {"exact": 0, "skel": 1, "weak": 2}.get(x["best_level"], 3)
        return (lvl, -x["best_support"], x["id"])

    rows.sort(key=rank)
    summary = {
        "active_unvalidated": len(rows),
        "with_exact": sum(1 for x in rows if x["best_level"] == "exact"),
        "with_skel": sum(1 for x in rows if x["best_level"] == "skel"),
        "with_weak_only": sum(1 for x in rows if x["best_level"] == "weak"),
        "with_none": sum(1 for x in rows if x["best_level"] == "none"),
        "with_lit_hint": sum(1 for x in rows if x["literature_hint"]),
        "with_doi_in_notes": sum(1 for x in rows if x["doi_in_notes"]),
    }
    OUT_JSON.write_text(json.dumps({"summary": summary, "rows": rows},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Rule evidence links (active unvalidated)", "",
             "- rules: **%d**" % len(rows),
             "- exact template match: **%d**" % summary["with_exact"],
             "- skeleton match: **%d**" % summary["with_skel"],
             "- weak containment only: **%d**" % summary["with_weak_only"],
             "- no ORD template evidence: **%d**" % summary["with_none"],
             "- notes with journal/year hint: %d" % summary["with_lit_hint"],
             "- notes with DOI: %d" % summary["with_doi_in_notes"], "",
             "| rule | category | level | ORD support | lit hint | DOI |",
             "|---|---|---|---:|---|---|"]
    for x in rows:
        lines.append("| `%s` | %s | %s | %d | %s | %s |" %
                     (x["id"], x["category"], x["best_level"],
                      x["best_support"], x["literature_hint"] or "",
                      x["doi_in_notes"] or ""))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print("written", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
