"""Audit internal consistency of the manuscript: collect every numeric claim by
metric and show where each appears, so cross-section conflicts are visible.

Read-only. Usage:
    python tools/audit_paper_consistency.py [md ...]

With no arguments it audits the two PeerJ markdown versions (EN + ZH).
"""
from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

STAGE = Path(__file__).resolve().parent.parent
PAPER = STAGE / "reports" / "paper" / "arxiv-20261020"
DEFAULT = [
    PAPER / "manuscript-peerj-humanizer-20261030.md",
    PAPER / "manuscript-peerj-humanizer-20261030-zh.md",
]

# metric name -> regex that captures the value
METRICS = OrderedDict([
    ("forward_recall", r"(\d{2}\.\d{1,2})\s*%\s*(?:single-step recall|的单步召回|召回率)"),
    ("recall_phrase", r"(?:recall|召回)[^\n]{0,40}?(\d{2}\.\d{2})\s*%"),
    ("top1", r"top-1[^\n\d]{0,30}(\d{1,3}\.\d{1,2})\s*%"),
    ("candidate_mean", r"(?:mean of|平均候选数?[为]?)\s*(\d{1,3}\.\d)\s*(?:candidates|个候选)"),
    ("wilson_ci", r"CI\s*(\d{2}\.\d{2})\s*(?:%|至|to)\s*(\d{2}\.\d{2})"),
    ("runtime_s", r"(\d[\d,]{2,6})\s*(?:seconds|秒)"),
    ("n_reactions", r"([\d,]{4,7})\s*(?:USPTO-50k reactions|条 USPTO-50k 反应|条反应)"),
    ("n_targets", r"([\d,]{3,6})\s*(?:targets|个目标)"),
    ("n_templates", r"([\d,]{3,7})\s*(?:templates|条模板)"),
    ("reverse_any", r"(?:any-hit)[^\n]{0,60}?(\d{2}\.\d{2})\s*%"),
])


def sections(lines):
    """Yield (section title, start line index 0-based) for each heading."""
    out = []
    for i, ln in enumerate(lines):
        if re.match(r"^#{1,4}\s+\S", ln):
            out.append((ln.strip("# ").strip(), i))
    return out


def section_of(starts, idx):
    name = "(front matter)"
    for title, at in starts:
        if at <= idx:
            name = title
        else:
            break
    return name


def audit(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    starts = sections(lines)
    hits = {k: [] for k in METRICS}
    for i, ln in enumerate(lines):
        for name, pat in METRICS.items():
            for m in re.finditer(pat, ln, flags=re.IGNORECASE):
                vals = tuple(g for g in m.groups() if g)
                hits[name].append({
                    "value": "|".join(vals),
                    "line": i + 1,
                    "section": section_of(starts, i),
                    "ctx": ln.strip()[:150],
                })
    return hits


def main(argv):
    files = [Path(a) for a in argv[1:]] or DEFAULT
    for path in files:
        if not path.exists():
            print("missing:", path)
            continue
        hits = audit(path)
        print("=" * 100)
        print(path.name, f"({path.stat().st_size} bytes)")
        for name, items in hits.items():
            if not items:
                continue
            vals = sorted({h["value"] for h in items})
            flag = "  <-- MULTIPLE VALUES" if len(vals) > 1 else ""
            print(f"\n[{name}] {len(items)} hits, distinct={len(vals)}: {', '.join(vals)}{flag}")
            for h in items:
                print(f"    L{h['line']:<5} {h['section'][:34]:<34} {h['value']:<14} {h['ctx'][:80]}")
        print()


if __name__ == "__main__":
    main(sys.argv)
