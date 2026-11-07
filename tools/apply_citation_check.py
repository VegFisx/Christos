#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 verify_citations.py 的结果写回证据文件（只改元数据，不改任何数值/结论）。

规则（对应 AGENTS §十二「底层反应逻辑参数必须有参考文献」）：
  1. 每条带 doi 的记录增加 `citation_check` 字段：
     - status = verified / metadata_mismatch / doi_not_registered / not_in_crossref
     - checked_at 时间戳、crossref_title/crossref_year 原始记录、note。
  2. 标题以 Crossref 记录为准（我们自己抄的标题与官方记录不一致时覆盖，并留
     `title_ours` 备份），**期刊/年份不一致只登记不改**。
  3. DOI 在 doi.org 上解析不到（404）的记录：标 `doi_not_registered`，
     `doi_valid: false`；若该记录另有可访问 url，则保留 url 并登记 `url_ok`。
  4. 不改任何 preset 数值、不改 status 判定（supported/not_found 等结论层字段）。
"""
import json
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "reports" / "citation_check.json"
FILES = [
    "rules/paozhi_evidence.json",
    "rules/literature_evidence.json",
    "conditions/kinetics_measurements.json",
    "conditions/template_verification_20261106.json",
    "reports/paper/paozhi_sources_20261031.json",
]
# doi.org 解析 302 的（真实注册）；404 的（未注册）
DOI_302 = {
    "10.13422/j.cnki.syfjx.20241061", "10.14148/j.issn.1672-0482.2012.03.024",
    "10.19540/j.cnki.cjcmm.20221111.301", "10.19540/j.cnki.cjcmm.20250526.301",
    "10.7501/j.issn.0253-2670.2019.21.018",
}
DOI_404 = {
    "10.13422/j.cnki.syfjx.20250561",
    "10.7501/j.issn.0253-2670.2025.09.010",
    "10.7501/j.issn.0253-2670.2026.06.008",
}
URL_OK = {
    "10.7501/j.issn.0253-2670.2025.09.010":
        "https://www.tiprpress.com/zcy/ch/reader/create_pdf.aspx"
        "?file_no=20250910&year_id=2025&quarter_id=9&falg=1",
}
NOW = time.strftime("%Y-%m-%dT%H:%M:%S")


def load_check():
    d = json.loads(CHECK.read_text(encoding="utf-8"))
    out = {}
    for r in d["rows"]:
        out[r["doi"].lower()] = r
    return out


def patch(obj, res, stats):
    if isinstance(obj, dict):
        doi = ""
        for k, v in obj.items():
            if k.lower() == "doi" and isinstance(v, str):
                doi = v.strip().lower()
                doi = doi.replace("https://doi.org/", "").rstrip(".")
        if doi:
            r = res.get(doi)
            if r:
                cr = r.get("crossref") or {}
                cc = {
                    "status": r["status"],
                    "checked_at": NOW,
                    "by": "tools/verify_citations.py (Crossref + EuropePMC + OpenAlex)",
                }
                if cr.get("title"):
                    cc["crossref_title"] = cr["title"]
                    cc["crossref_journal"] = cr.get("journal", "")
                    cc["crossref_year"] = cr.get("year", "")
                    ours = obj.get("title") or ""
                    if not ours:
                        src = obj.get("source") or {}
                        ours = src.get("title") or "" if isinstance(src, dict) else ""
                    if ours and ours.strip().lower() != cr["title"].strip().lower():
                        overlap = (r.get("compare") or {}).get("title_overlap")
                        if overlap is not None and overlap < 0.95:
                            # 以官方记录为准；保留原写法备查
                            target = obj if obj.get("title") else obj.get("source", {})
                            if isinstance(target, dict) and target.get("title"):
                                target["title_ours"] = target["title"]
                                target["title"] = cr["title"]
                                stats["title_fixed"] += 1
                if doi in DOI_404:
                    cc["status"] = "doi_not_registered"
                    cc["note"] = "doi.org 解析 404：该 DOI 未注册，出处需重查。"
                    obj["doi_valid"] = False
                    if doi in URL_OK:
                        cc["url_ok"] = URL_OK[doi]
                        obj["url"] = obj.get("url") or URL_OK[doi]
                    stats["doi_invalid"] += 1
                elif doi in DOI_302:
                    cc["note"] = "doi.org 解析 302（中文库 DOI，Crossref 无记录）。"
                    obj["doi_valid"] = True
                    stats["doi_cn_ok"] += 1
                ep = r.get("europepmc") or {}
                if ep.get("pmcid"):
                    cc["pmcid"] = ep["pmcid"]
                    cc["open_access"] = ep.get("is_open_access")
                oa = r.get("openalex") or {}
                if oa.get("oa_url"):
                    cc["oa_url"] = oa["oa_url"]
                obj["citation_check"] = cc
                stats["patched"] += 1
        for v in obj.values():
            patch(v, res, stats)
    elif isinstance(obj, list):
        for v in obj:
            patch(v, res, stats)


def main():
    res = load_check()
    stats = {"patched": 0, "title_fixed": 0, "doi_invalid": 0, "doi_cn_ok": 0}
    for rel in FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        before = stats["patched"]
        patch(data, res, stats)
        if stats["patched"] != before:
            p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print("patched %-55s +%d" % (rel, stats["patched"] - before))
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
