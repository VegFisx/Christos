"""Audit the manuscript reference list against Crossref, and check in-text citations.

Read-only. Writes reports/reference_audit_<date>.json.
"""

import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "reports/paper/arxiv-20261020/manuscript-peerj-humanizer-20261030.md"
OUT = ROOT / "reports" / f"reference_audit_{date.today():%Y%m%d}.json"
CURL = "curl.exe"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def tokens(s: str):
    return [t for t in norm(s).split() if len(t) > 2]


def overlap(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    hit = sum(1 for t in ta if t in tb)
    return hit / max(len(ta), 1)


def crossref(doi: str):
    out = subprocess.run(
        [CURL, "-sS", "--max-time", "25", "-A", "reference-audit/1.0 (mailto:vegfish@qq.com)",
         f"https://api.crossref.org/works/{doi}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return json.loads(out.stdout)["message"]
    except Exception:
        return None


def resolves(doi: str) -> bool:
    """true when doi.org redirects (302/301) even if Crossref has no record."""
    out = subprocess.run([CURL, "-sS", "-o", "NUL", "-w", "%{http_code}", "--max-time", "20",
                          f"https://doi.org/{doi}"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout.strip() in ("301", "302", "303", "307", "308")


def parse_entries(text: str):
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("## References"))
    block = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        block.append(line)
    entries, cur = [], None
    for line in block:
        m = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if m:
            if cur:
                entries.append(cur)
            cur = {"n": int(m.group(1)), "text": m.group(2)}
        elif cur is not None and line.strip():
            cur["text"] += " " + line.strip()
    if cur:
        entries.append(cur)
    return entries


def first_author_year(text: str):
    m = re.match(r"^([^,(]+)", text)
    author = (m.group(1) if m else "").strip()
    surname = author.split()[-1] if author else ""
    y = re.search(r"\((\d{4})[a-z]?\)", text)
    return surname, (y.group(1) if y else "")


def main():
    text = PAPER.read_text(encoding="utf-8")
    entries = parse_entries(text)
    body = text.split("## References")[0]

    results = []
    for e in entries:
        doi = re.search(r"https?://doi\.org/(\S+)", e["text"])
        url = re.search(r"https?://(?!doi\.org)(\S+)", e["text"])
        rec = {"n": e["n"], "surname": first_author_year(e["text"])[0],
               "year": first_author_year(e["text"])[1],
               "doi": doi.group(1).rstrip(".,)") if doi else None,
               "url": url.group(1).rstrip(".,)") if url else None,
               "title": e["text"], "status": "manual", "notes": []}
        if rec["doi"]:
            m = crossref(rec["doi"])
            if not m:
                rec["status"] = "not_in_crossref" if resolves(rec["doi"]) else "doi_unresolved"
            else:
                ct = (m.get("title") or [""])[0]
                rec["crossref_title"] = ct
                # Prefer the print year: that is what a citation should carry.
                pp = (m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[""]]
                rec["crossref_year"] = str(pp[0][0])
                rec["crossref_journal"] = (m.get("container-title") or [""])[0]
                rec["crossref_volume"] = m.get("volume")
                rec["crossref_pages"] = m.get("page")
                ov = overlap(ct, e["text"])
                rec["title_overlap"] = round(ov, 3)
                rec["status"] = "ok" if ov >= 0.7 else "title_mismatch"
                if rec["year"] and rec["crossref_year"] and rec["year"] != rec["crossref_year"]:
                    rec["status"] = "year_mismatch" if rec["status"] == "ok" else rec["status"]
                    rec["notes"].append(f"year {rec['year']} vs Crossref {rec['crossref_year']}")
        results.append(rec)

    # in-text citations: narrative (Surname et al. (2020)), parenthetical
    # (Surname et al., 2020), and the table form "Fu et al., 2017".
    cites = set()
    patterns = (
        r"([A-Z][A-Za-z\-]+)(?:\s+et al\.|\s*&\s*[A-Z][A-Za-z\-]+)?\s*\((\d{4})\)",
        r"([A-Z][A-Za-z\-]+)(?:\s+et al\.|\s*&\s*[A-Z][A-Za-z\-]+)?,\s*(\d{4})",
    )
    for pat in patterns:
        for m in re.finditer(pat, body):
            cites.add((m.group(1), m.group(2)))
    # "Richard et al., 2016, 2021" cites two years of one surname
    for m in re.finditer(r"([A-Z][A-Za-z\-]+)(?:\s+et al\.)?,\s*(\d{4}),\s*(\d{4})\b", body):
        cites.add((m.group(1), m.group(2)))
        cites.add((m.group(1), m.group(3)))
    listed = {(r["surname"], r["year"]) for r in results}
    missing = sorted(c for c in cites if c not in listed)
    uncited = sorted(p for p in listed if p and p not in cites)

    summary = {
        "n_entries": len(results),
        "status_counts": {},
        "in_text_citations": len(cites),
        "cited_not_listed": missing,
        "listed_not_cited": uncited,
    }
    for r in results:
        summary["status_counts"][r["status"]] = summary["status_counts"].get(r["status"], 0) + 1

    OUT.write_text(json.dumps({"summary": summary, "entries": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    bad = [r for r in results if r["status"] not in ("ok", "manual")]
    if bad:
        print("\n需要处理：")
        for r in bad:
            print(f"  [{r['n']}] {r['status']}  doi={r['doi']}")
            print(f"      ours : {r['title'][:120]}")
            if r.get("crossref_title"):
                print(f"      cross: {r['crossref_title'][:120]}  ({r['crossref_year']}, {r['crossref_journal']})")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
