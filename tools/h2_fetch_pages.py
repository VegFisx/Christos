# -*- coding: utf-8 -*-
r"""H2 · 搜索引擎拿不到的那几条，直接打站点页面取证。

顺序：医学百科（yixue.com）→ A+医学百科（a-hospital.com）→ 维基百科（zh）
     → 维基文库搜索（zh.wikisource）
命中判据：页面文本里出现**方名**。找到就停下并保存该页正文节选（留证）。

用法：``python tools\h2_fetch_pages.py``   （读 data\h2_refetch.json 的 weak 列表）
"""
from __future__ import annotations

import json
import re
import sys
import argparse
import time
import urllib.parse
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_fetch import fetch, strip_tags                     # noqa: E402

NET = STAGE / "reports" / "_h2_net"
REFS = STAGE / "data" / "h2_refetch.json"
SAMPLE = STAGE / "data" / "h2_sample.json"

SITES = [
    ("医学百科", "https://www.yixue.com/index.php?search={q}"),
    ("A+医学百科", "http://www.a-hospital.com/w/{q}"),
    ("维基百科", "https://zh.wikipedia.org/wiki/{q}"),
    ("维基文库", "https://zh.wikisource.org/w/index.php?search={q}"),
]


def excerpt(text: str, name: str, width: int = 900) -> str:
    """截取以方名附近为中心的正文（先去掉脚本/样式）。"""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    t = strip_tags(t)
    i = t.find(name)
    if i < 0:
        return t[:width]
    lo = max(0, i - 120)
    return t[lo:lo + width]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=str(SAMPLE))
    ap.add_argument("--outdir", default=str(NET))
    ap.add_argument("--refs", default=str(REFS), help="待抓序号清单（weak 列表）")
    ap.add_argument("--all", action="store_true", help="忽略 weak 列表，全部抓")
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--start", type=int, default=0, help="只抓序号 ≥ 这个数的（分小批跑）")
    ap.add_argument("--limit", type=int, default=10 ** 6)
    a = ap.parse_args()
    net = Path(a.outdir)
    net.mkdir(parents=True, exist_ok=True)
    items = {x["序号"]: x for x in
             json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]}
    if a.all:
        weak = sorted(items)
    else:
        weak = json.loads(Path(a.refs).read_text(encoding="utf-8"))["weak"]
    weak = [n for n in weak if n >= a.start][:a.limit]
    print("=" * 100)
    print("H2 · 直接页面取证：%d 条" % len(weak))
    print("=" * 100)
    n_hit = n_miss = 0
    for n in weak:
        x = items[n]
        got = None
        for label, tmpl in SITES:
            url = tmpl.replace("{q}", urllib.parse.quote(x["方名"]))
            try:
                html = fetch(url, timeout=25)
            except Exception as ex:                        # noqa: BLE001 —— 打印+继续
                print("      [%s] %s: %s" % (label, type(ex).__name__, str(ex)[:60]))
                time.sleep(1.5)
                continue
            txt = excerpt(html, x["方名"])
            if x["方名"] in txt:
                got = {"site": label, "url": url, "excerpt": txt[:1200]}
                break
            time.sleep(1.5)
        fp = net / ("%03d_%s.page.json" % (n, re.sub(r"[^\w\u4e00-\u9fff]", "_", x["方名"])))
        fp.write_text(json.dumps({"序号": n, "方名": x["方名"], "出处": x["出处"],
                                  "组成": x["组成"], "page": got,
                                  "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                                 ensure_ascii=False, indent=1), encoding="utf-8")
        if got:
            n_hit += 1
            print("  #%03d %-12s ✔ %s ｜ %s" % (n, x["方名"][:12], got["site"],
                                                got["excerpt"][:70].replace("\n", " ")))
        else:
            n_miss += 1
            print("  #%03d %-12s ✘ 四个站点都没有可用页面" % (n, x["方名"][:12]))
        time.sleep(a.sleep)
    print()
    print("  命中页面 %d ｜ 没命中 %d" % (n_hit, n_miss))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
