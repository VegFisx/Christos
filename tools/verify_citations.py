#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对项目里登记的文献引证（DOI / 标题 / 期刊 / 年份 / 可开放获取性）。

为什么需要这个：
    项目里所有"有出处"的参数都靠一份 DOI + 引句支撑（rules/paozhi_evidence.json、
    rules/literature_evidence.json、conditions/kinetics_measurements.json、
    conditions/template_verification_20261106.json、reports/paper/paozhi_sources_*.json）。
    但 DOI 是否真实、标题期刊年份是否对得上，一直只是人工抄录，没有机器核对过。

口径：
    1. 只核对**元数据**（DOI 是否存在、标题/期刊/年份是否与我们写的一致）；
       原文引句是否属实，仍需回原文，本脚本不做结论，只标出可开放获取的入口。
    2. 网络走 curl 子进程（Python urllib 不走系统代理，实测会失败）。
    3. 任何一条查不到，结论是 `not_found`，**不推测**、不改动任何证据文件。

用法：
    python tools/verify_citations.py [-o reports/citation_check.json] [--limit N]
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_FILES = [
    "rules/paozhi_evidence.json",
    "rules/literature_evidence.json",
    "conditions/kinetics_measurements.json",
    "conditions/template_verification_20261106.json",
    "reports/paper/paozhi_sources_20261031.json",
]
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"',;)\]]+")


def _walk(obj, path="", out=None):
    """递归收集带 doi 的字典节点（保留其同级字段）。"""
    if out is None:
        out = []
    if isinstance(obj, dict):
        if any(k.lower() == "doi" for k in obj):
            out.append((path, obj))
        for k, v in obj.items():
            _walk(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk(v, "%s[%d]" % (path, i), out)
    return out


def collect():
    """返回 {doi: {files:[], claimed:{title,journal,year,quotes:[]}}}。"""
    reg = {}
    for rel in EVIDENCE_FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for path, node in _walk(data):
            doi = ""
            for k, v in node.items():
                if k.lower() == "doi" and isinstance(v, str):
                    doi = v.strip()
            if not doi:
                continue
            doi = doi.lower().replace("https://doi.org/", "").rstrip(".")
            ent = reg.setdefault(doi, {"files": [], "paths": [], "claimed": {}})
            ent["files"].append(rel)
            ent["paths"].append(path)
            for k, v in node.items():
                kl = k.lower()
                if kl in ("title", "journal", "year", "year_published"):
                    key = "year" if kl.startswith("year") else kl
                    if isinstance(v, (str, int)) and str(v):
                        ent["claimed"].setdefault(key, str(v))
                if kl in ("quote", "quoted", "evidence_quote") and isinstance(v, str):
                    ent["claimed"].setdefault("quotes", []).append(v[:300])
    for doi, ent in reg.items():
        ent["files"] = sorted(set(ent["files"]))
    return reg


def _curl_json(url, timeout=30):
    try:
        r = subprocess.run(["curl", "-sS", "--max-time", str(timeout), url],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except Exception as exc:  # curl 不在 PATH
        return None, "curl_error:%s" % exc
    if r.returncode != 0:
        return None, (r.stderr or "").strip()[:200]
    try:
        return json.loads(r.stdout), ""
    except Exception:
        return None, "not_json"


def crossref(doi):
    data, err = _curl_json("https://api.crossref.org/works/%s" % doi)
    if not data:
        return None, err
    msg = data.get("message") or {}
    title = (msg.get("title") or [""])[0]
    journal = (msg.get("container-title") or [""])[0]
    year = ""
    for k in ("published-print", "published-online", "issued", "created"):
        parts = ((msg.get(k) or {}).get("date-parts") or [[None]])[0]
        if parts and parts[0]:
            year = str(parts[0])
            break
    return {"title": title, "journal": journal, "year": year,
            "type": msg.get("type", ""), "publisher": msg.get("publisher", "")}, ""


def europepmc(doi):
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
           + "?query=DOI:%22" + doi + "%22&format=json&resultType=lite")
    data, err = _curl_json(url)
    if not data:
        return None, err
    res = ((data.get("resultList") or {}).get("result") or [])
    if not res:
        return None, "no_record"
    r = res[0]
    return {"in_epmc": r.get("inEPMC", "N"), "is_open_access": r.get("isOpenAccess", "N"),
            "has_pdf": r.get("hasPDF", "N"), "pmcid": r.get("pmcid", ""),
            "openalex_free": ""}, ""


def openalex(doi):
    data, err = _curl_json("https://api.openalex.org/works/doi:%s" % doi)
    if not data:
        return None, err
    loc = data.get("best_oa_location") or {}
    return {"is_oa": bool((data.get("open_access") or {}).get("is_oa")),
            "oa_url": loc.get("pdf_url") or loc.get("landing_page_url") or "",
            "title": data.get("title", ""), "year": str(data.get("publication_year") or "")}, ""


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def compare(claimed, found):
    """标题比 token 重合率；年份严格比；期刊只比是否互含。"""
    out = {}
    ct, ft = _norm(claimed.get("title", "")), _norm(found.get("title", ""))
    if ct and ft:
        a, b = set(ct.split()), set(ft.split())
        out["title_overlap"] = round(len(a & b) / max(1, len(a)), 3)
    if claimed.get("year") and found.get("year"):
        out["year_match"] = claimed["year"] == found["year"]
        out["year_claimed"] = claimed["year"]
        out["year_found"] = found["year"]
    cj, fj = _norm(claimed.get("journal", "")), _norm(found.get("journal", ""))
    if cj and fj:
        out["journal_match"] = (cj in fj) or (fj in cj)
    return out


def resolve_doi(doi):
    """用 doi.org 解析一次：302/301 = 已注册（可能在中文库里），404 = 未注册。"""
    try:
        r = subprocess.run(["curl", "-sS", "-o", "NUL", "-w", "%{http_code}",
                            "--max-time", "25", "https://doi.org/" + doi],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
    except Exception as exc:
        return "error:%s" % exc
    code = (r.stdout or "").strip()
    return code or "empty"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/citation_check.json")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    reg = collect()
    dois = sorted(reg)
    if args.limit:
        dois = dois[:args.limit]
    print("登记 DOI 去重后 %d 条，开始核对……" % len(dois))

    rows = []
    counts = {"verified": 0, "metadata_mismatch": 0, "not_found": 0, "no_claimed": 0}
    for i, doi in enumerate(dois, 1):
        ent = reg[doi]
        claimed = ent.get("claimed", {})
        cr, cr_err = crossref(doi)
        ep, _ = europepmc(doi)
        oa, _ = openalex(doi)
        row = {"doi": doi, "files": ent["files"], "paths": ent["paths"],
               "claimed": claimed, "crossref": cr, "europepmc": ep, "openalex": oa,
               "crossref_error": cr_err}
        if not cr:
            # Crossref 查不到时，用 doi.org 判断这个 DOI 到底是不是注册过
            # （中文库 DOI 普遍不向 Crossref 报送，但 doi.org 能解析）
            code = resolve_doi(doi)
            row["doi_org"] = code
            if code in ("301", "302", "303", "307", "308"):
                row["status"] = "not_in_crossref_resolvable"
            else:
                row["status"] = "not_found"
        else:
            cmp = compare(claimed, cr)
            row["compare"] = cmp
            bad = []
            if cmp.get("year_match") is False:
                bad.append("year")
            if cmp.get("journal_match") is False:
                bad.append("journal")
            if cmp.get("title_overlap") is not None and cmp["title_overlap"] < 0.5:
                bad.append("title")
            if not claimed.get("title"):
                counts["no_claimed"] += 1
                row["status"] = "verified_notitle"
            elif bad:
                row["status"] = "metadata_mismatch"
                row["bad_fields"] = bad
            else:
                row["status"] = "verified"
        counts[row["status"]] = counts.get(row["status"], 0) + 1
        rows.append(row)
        cr_txt = (cr or {}).get("title", "")[:60]
        print("  [%2d/%d] %-40s %-18s %s" % (i, len(dois), doi, row["status"], cr_txt))
        time.sleep(0.2)

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "n_dois": len(dois), "counts": counts, "rows": rows,
           "note": ("只核对元数据；引句是否属实仍需回原文。"
                    "not_found 表示 Crossref 无记录（不等于文献不存在，可能是中文库 DOI）。")}
    p = ROOT / args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n汇总：%s" % json.dumps(counts, ensure_ascii=False))
    print("写出 %s" % p)


if __name__ == "__main__":
    main()
