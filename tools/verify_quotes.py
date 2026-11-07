#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对证据文件里的「引句」是否真的出现在文献正文里（能拿到开放全文的才判）。

与 verify_citations.py 的分工：
    verify_citations.py —— 元数据（DOI/标题/期刊/年份）是否对得上；
    本脚本            —— 引句（quote）在正文里是否找得到。

口径：
    1. 只用**开放获取全文**（EuropePMC 的 fullTextXML，OA 子集）；
       拿不到全文的一律记 `no_full_text`，**不推测引句真假**。
    2. 判定用归一化后的 5-gram 覆盖率（对空格/换行/软连字符做归一）：
         >=0.95  verbatim      引句几乎逐字出现
         >=0.75  minor_diff    只差少量词（改述/断句/漏字）
         >=0.40  paraphrase    意思在，文字改写过
         < 0.40  absent        正文里没有（或文献无关）
    3. 不改动任何证据文件，只出报告。

用法：
    python tools/verify_quotes.py [-o reports/quote_check.json] [--rebuild]
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
CACHE = ROOT / "_diag" / "fulltext"
FILES = [
    "rules/paozhi_evidence.json",
    "rules/literature_evidence.json",
    "conditions/kinetics_measurements.json",
    "conditions/template_verification_20261106.json",
    "reports/paper/paozhi_sources_20261031.json",
]
CITATION = ROOT / "reports" / "citation_check.json"


def load_pmcid_map():
    """doi -> pmcid（来自上一轮的引证核对结果）。"""
    if not CITATION.exists():
        return {}
    d = json.loads(CITATION.read_text(encoding="utf-8"))
    out = {}
    for r in d.get("rows", []):
        ep = r.get("europepmc") or {}
        if ep.get("pmcid"):
            out[r["doi"].lower()] = ep["pmcid"]
    return out


def walk(obj, path="", out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        if any(k.lower() == "doi" for k in obj):
            out.append((path, obj))
        for k, v in obj.items():
            walk(v, "%s.%s" % (path, k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, "%s[%d]" % (path, i), out)
    return out


def collect():
    """收集 (doi, quote, file, path) —— 引句可能挂在 doi 节点或其 source 子节点上。"""
    items = []
    for rel in FILES:
        p = ROOT / rel
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for path, node in walk(data):
            doi = ""
            for k, v in node.items():
                if k.lower() == "doi" and isinstance(v, str):
                    doi = v.strip()
            if not doi:
                continue
            doi = doi.lower().replace("https://doi.org/", "").rstrip(".")
            quotes = []
            for k, v in node.items():
                if k.lower() == "quote" and isinstance(v, str) and len(v.strip()) > 20:
                    quotes.append(v.strip())
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        if k2.lower() == "quote" and isinstance(v2, str) and len(v2.strip()) > 20:
                            quotes.append(v2.strip())
            for q in quotes:
                items.append({"doi": doi, "quote": q, "file": rel, "path": path})
    return items


def fetch_fulltext(pmcid, rebuild=False):
    """取 EuropePMC 全文 XML（缓存到 _diag/fulltext/<pmcid>.xml）。返回 (xml|None, note)。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / ("%s.xml" % pmcid)
    if p.exists() and not rebuild and p.stat().st_size > 1000:
        return p.read_text(encoding="utf-8", errors="replace"), "cache"
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/%s/fullTextXML" % pmcid
    try:
        r = subprocess.run(["curl", "-sS", "--max-time", "60", "-o", str(p), url],
                           capture_output=True, text=True)
    except Exception as exc:
        return None, "curl_error:%s" % exc
    if not p.exists() or p.stat().st_size < 1000:
        return None, "no_xml"
    return p.read_text(encoding="utf-8", errors="replace"), "fetched"


_TAG = re.compile(r"<[^>]+>")


def to_text(xml):
    t = _TAG.sub(" ", xml)
    t = t.replace("&#x2013;", "-").replace("&#x2014;", "-").replace("&amp;", "&")
    t = t.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
    return t


def norm(s):
    s = s.lower()
    s = re.sub(r"[\u00ad\u200b]", "", s)
    s = re.sub(r"[\u2018\u2019\u201c\u201d]", "'", s)
    # 各种连字符/减号统一（文献里 h−1、h-1、h–1 混用，不统一会误判为改述）
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2212\u00b1]", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def flat(s):
    """去掉所有空白与标点，只留字母/数字/CJK —— 用于抗排版差异的字符级比对。"""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", norm(s))


def char_ratio(text, quote, n=8):
    a, b = flat(text), flat(quote)
    if len(b) < n:
        return 0.0
    qg = {b[i:i + n] for i in range(len(b) - n + 1)}
    tg = {a[i:i + n] for i in range(len(a) - n + 1)}
    if not qg:
        return 0.0
    return len(qg & tg) / len(qg)


def ngrams(s, n=5):
    toks = s.split()
    if len(toks) < n:
        return {" ".join(toks)} if toks else set()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def judge(text, quote):
    t, q = norm(text), norm(quote)
    if not q:
        return None, 0.0
    qg = ngrams(q)
    tg = ngrams(t)
    word = len(qg & tg) / len(qg) if qg else 0.0
    char = char_ratio(text, quote)
    ratio = max(word, char)
    if ratio >= 0.95:
        v = "verbatim"
    elif ratio >= 0.75:
        v = "minor_diff"
    elif ratio >= 0.40:
        v = "paraphrase"
    else:
        v = "absent"
    return v, round(ratio, 3)


def fetch_abstract(doi):
    """拿不到全文时的退路：EuropePMC 摘要（很多付费刊的摘要仍可读）。"""
    url = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
           + "?query=DOI:%22" + doi + "%22&format=json&resultType=core")
    try:
        r = subprocess.run(["curl", "-sS", "--max-time", "40", url],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        data = json.loads(r.stdout)
    except Exception:
        return None
    res = ((data.get("resultList") or {}).get("result") or [])
    if not res:
        return None
    ab = res[0].get("abstractText") or ""
    ab = re.sub(r"<[^>]+>", " ", ab)
    return ab if len(ab) > 200 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="reports/quote_check.json")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    pm = load_pmcid_map()
    items = collect()
    print("待核引句 %d 条，涉及 %d 个 DOI" % (len(items), len({i["doi"] for i in items})))

    texts, notes = {}, {}
    for doi, pmcid in pm.items():
        xml, note = fetch_fulltext(pmcid, args.rebuild)
        notes[pmcid] = note
        if xml:
            texts[doi] = to_text(xml)
            print("  fulltext ok  %-32s %s (%s, %d chars)" % (doi, pmcid, note, len(texts[doi])))

    rows = []
    counts = {}
    abstracts = {}
    for it in items:
        doi = it["doi"]
        if doi not in texts:
            if doi not in abstracts:
                abstracts[doi] = fetch_abstract(doi)
            ab = abstracts.get(doi)
            if ab:
                v, r = judge(ab, it["quote"])
                row = dict(it, verdict="abstract_%s" % v, ratio=r,
                           note="只拿到摘要（付费刊/中文库）")
            else:
                row = dict(it, verdict="no_full_text", ratio=0.0,
                           note="未取得全文也未取得摘要")
        else:
            v, r = judge(texts[doi], it["quote"])
            row = dict(it, verdict=v, ratio=r, pmcid=pm[doi])
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        rows.append(row)
        print("  [%-18s] %-32s r=%.3f  %s" % (
            row["verdict"], doi, row["ratio"], it["quote"][:44].replace("\n", " ")))

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "n_quotes": len(items), "counts": counts,
           "pmcid_map": pm, "fetch_notes": notes,
           "method": "5-gram coverage of normalized quote against EuropePMC fullTextXML",
           "note": "no_full_text 表示拿不到开放全文，不是引句有问题。"}
    p = ROOT / args.out
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n汇总：%s" % json.dumps(counts, ensure_ascii=False))
    print("写出 %s" % p)


if __name__ == "__main__":
    main()
