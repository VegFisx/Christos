# -*- coding: utf-8 -*-
"""Re-query the H2 records previously marked as missing from public sources.

This script does not modify the original H2 sample, verdicts, or evidence.
It writes a separate DuckDuckGo evidence set and a coverage suggestion table.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_judge_sheet import coverage, ingredients


def real_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return target
    return url


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
            )
        },
    )
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read().decode("utf-8", "replace")
        except Exception as exc:  # noqa: BLE001 - retry transient TLS failures
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def strip_tags(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


def parse_results(page: str) -> list[dict]:
    link_re = re.compile(
        r'<a\b(?=[^>]*class="[^"]*result__a[^"]*")(?=[^>]*href="([^"]+)")[^>]*>'
        r"(.*?)</a>",
        re.S,
    )
    snippet_re = re.compile(
        r'<a\b(?=[^>]*class="[^"]*result__snippet[^"]*")(?=[^>]*href="([^"]+)")[^>]*>'
        r"(.*?)</a>",
        re.S,
    )
    links = link_re.findall(page)
    snippets = snippet_re.findall(page)
    results = []
    for index, (href, title) in enumerate(links):
        snippet = snippets[index][1] if index < len(snippets) else ""
        results.append({
            "title": strip_tags(title),
            "url": real_url(html.unescape(href)),
            "snippet": strip_tags(snippet),
        })
    return results


def load_items() -> dict[tuple[int, int], dict]:
    rows = {}
    for batch, name in ((1, "h2_sample.json"), (2, "h2_sample2.json")):
        data = json.loads((STAGE / "data" / name).read_text(encoding="utf-8"))
        for item in data["items"]:
            rows[(batch, int(item["序号"]))] = item
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--out", default=str(STAGE / "reports" / "_h2_recheck_20261018"))
    args = parser.parse_args()

    verdicts = json.loads((STAGE / "data" / "h2_verdicts_all.json").read_text(encoding="utf-8"))
    misses = [row for row in verdicts if row.get("判定") == "查无"]
    items = load_items()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = 0

    for row in misses:
        key = (int(row["批次"]), int(row["序号"]))
        item = items[key]
        book = re.search(r"《([^》]+)》", item.get("出处") or "")
        book_name = book.group(1) if book else ""
        query = f'{item["方名"]} {book_name} 组成'
        url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
        stem = f"b{key[0]}_{key[1]:03d}_{item['方名']}"
        try:
            page = fetch(url)
        except Exception as exc:  # noqa: BLE001 - count every failed query
            failures += 1
            rows.append({**row, "query": query, "engine": "duckduckgo_html",
                         "error": f"{type(exc).__name__}: {exc}", "results": []})
            print(f"FAIL {stem} {type(exc).__name__}: {exc}")
            continue

        (out / f"{stem}.html").write_text(page, encoding="utf-8")
        results = parse_results(page)[:10]
        (out / f"{stem}.json").write_text(
            json.dumps({"query": query, "engine": "duckduckgo_html", "results": results},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

        names = ingredients(item["组成"])
        best, best_result = 0, None
        for result in results:
            blob = html.unescape(result["title"] + " " + result["snippet"])
            hit, _ = coverage(names, blob)
            if hit > best:
                best, best_result = hit, result
        cov = round(best / max(1, len(names)), 3)
        has_named_evidence = any(item["方名"] in r["title"] + r["snippet"] for r in results)
        suggestion = "命中" if cov >= 0.6 else ("部分命中" if has_named_evidence else "查无")
        rows.append({
            **row,
            "复核建议": suggestion,
            "复核覆盖率": cov,
            "查询": query,
            "引擎": "duckduckgo_html",
            "结果数": len(results),
            "最佳来源": (best_result or {}).get("url", ""),
            "最佳摘要": (best_result or {}).get("snippet", ""),
            "证据文件": f"{stem}.json",
        })
        print(f"{stem}\tresults={len(results)}\tsuggestion={suggestion}\tcov={cov}")
        time.sleep(args.delay)

    (STAGE / "data" / "h2_recheck_misses.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    changed = sum(1 for row in rows if row.get("复核建议") in ("命中", "部分命中"))
    print(f"total={len(rows)} failures={failures} upgraded={changed}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
