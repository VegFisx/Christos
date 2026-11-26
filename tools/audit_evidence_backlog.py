# -*- coding: utf-8 -*-
"""Rank the active unvalidated rules by usage and literature hints.

It never edits rules.  Output:
  reports/evidence_backlog_20261124.json/.md

Columns per rule: category, dev hits, blind6 hits, notes excerpt, whether the
notes already name a journal/year (a hint, not yet a checked citation).
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "rules" / "rules.json"
OUT_JSON = ROOT / "reports" / "evidence_backlog_20261124.json"
OUT_MD = ROOT / "reports" / "evidence_backlog_20261124.md"

LIT_HINT = re.compile(r"(JACS|J\.?\s*Am\.?\s*Chem\.?\s*Soc|Angew|Org\.?\s*Lett|"
                      r"J\.?\s*Org\.?\s*Chem|Tetrahedron|Chem\.?\s*Rev|Nature|"
                      r"Science|IJMS|Molecules|Phytochemistry|J\.?\s*Ethnopharmacol)"
                      r"[^0-9]{0,20}(\d{4})", re.I)
DOI = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


def latest(pattern: str):
    fs = glob.glob(str(ROOT / pattern))
    return max(fs, key=lambda p: Path(p).stat().st_mtime) if fs else None


def rule_hit_counts(path):
    if not path or not Path(path).exists():
        return Counter()
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    c = Counter()
    for row in d.get("rows") or []:
        for rid in row.get("hit_rules") or []:
            c[rid] += 1
    return c


def main() -> int:
    d = json.loads(RULES.read_text(encoding="utf-8"))
    rules = d["rules"]
    active = [r for r in rules if str(r.get("status") or "active") == "active"]
    unv = [r for r in active if str(r.get("provenance") or "unvalidated") == "unvalidated"]

    dev_f = latest("reports/general_organic_full_lf_dev_*.json")
    blind_f = latest("reports/general_organic_full_lf_blind6_*.json")
    dev_hits = rule_hit_counts(dev_f)
    blind_hits = rule_hit_counts(blind_f)

    rows = []
    for r in unv:
        notes = r.get("notes") or ""
        lit = LIT_HINT.search(notes)
        doi = DOI.search(notes)
        rows.append({
            "id": r["id"],
            "category": r.get("category"),
            "dev_hits": dev_hits.get(r["id"], 0),
            "blind6_hits": blind_hits.get(r["id"], 0),
            "literature_hint": ("%s %s" % (lit.group(1), lit.group(2))) if lit else "",
            "doi_in_notes": doi.group(0) if doi else "",
            "notes": notes[:220],
        })
    rows.sort(key=lambda x: (-(x["dev_hits"] + x["blind6_hits"]), x["id"]))

    cats = Counter(x["category"] for x in rows)
    out = {
        "generated_at": "2026-11-24",
        "dev_file": Path(dev_f).name if dev_f else None,
        "blind6_file": Path(blind_f).name if blind_f else None,
        "active_unvalidated": len(rows),
        "by_category": dict(cats),
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Evidence backlog (active unvalidated rules)", "",
             "- active unvalidated: **%d**" % len(rows),
             "- dev source: `%s`" % out["dev_file"],
             "- blind6 source: `%s`" % out["blind6_file"],
             "- 用法：dev/blind6 命中数 = 该规则作为 curated 规则贡献过的案例数",
             "- `lit hint` 只是 notes 里出现的期刊+年份，**尚未核对**；`DOI` 同理", "",
             "| rule | category | dev | blind6 | lit hint | DOI |",
             "|---|---|---:|---:|---|---|"]
    for x in rows:
        lines.append("| `%s` | %s | %d | %d | %s | %s |" %
                     (x["id"], x["category"], x["dev_hits"], x["blind6_hits"],
                      x["literature_hint"] or "", x["doi_in_notes"] or ""))
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("active unvalidated", len(rows))
    print("top by usage:")
    for x in rows[:12]:
        print("  %-50s dev=%d blind6=%d %s" %
              (x["id"], x["dev_hits"], x["blind6_hits"], x["literature_hint"]))
    print("written", OUT_JSON, OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
