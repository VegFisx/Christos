# -*- coding: utf-8 -*-
r"""H2 · 给每条抽中记录抓**一个最可能的页面正文**（留证，供逐条判定）。

挑页顺序：先按"摘要里已命中的药材数"排，再优先这些站：
ouryao / 医学百科 / 百度百科 / 360百科 / 维基 / 中医世家 / a-hospital / 有来 / 民福康 /
家庭医生 / 大众养生 …（都是公开可访问的医药百科/方剂站）

输出：`reports\_h2_net\<序号>_<方名>.top.txt`（页面正文节选，最多 2500 字）
      并在 `data\h2_pages.json` 里登记 URL 与状态（抓不到就写明抓不到）。

用法：``python tools\h2_fetch_top.py --sleep 3``
"""
from __future__ import annotations

import argparse
import json
import re
import sys
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
from h2_judge_sheet import ingredients, coverage           # noqa: E402

NET = STAGE / "reports" / "_h2_net"
SAMPLE = STAGE / "data" / "h2_sample.json"
REG = STAGE / "data" / "h2_pages.json"

PREFER = ("ouryao.com", "yixue.com", "baike.baidu.com", "baike.so.com", "zh.wikipedia",
          "wikisource", "zysj.com", "a-hospital.com", "youlai.cn", "mfk.com",
          "familydoctor", "dazhongyi", "zhongyoo", "39.net", "jianke.com",
          "health.baidu.com", "ctext.org", "guoxuedashi", "zhongyibaike")
# 这些是**搜索站自己的跳转壳**，抓下来的是搜索页不是正文 —— 不当候选
SKIP = ("so.com/link", "/link?url=")


def real_url(u: str) -> str:
    """解开 DDG/360/sogou 的跳转链接，拿到目标站地址。"""
    if not u:
        return ""
    if u.startswith("//"):
        u = "https:" + u
    if "uddg=" in u:
        m = re.search(r"uddg=([^&]+)", u)
        if m:
            return urllib.parse.unquote(m.group(1))
    if u.startswith("/link?url="):
        return ""
    return u


def pick(item: dict, names: list) -> str:
    cands = []
    for fp in sorted(NET.glob("%03d_*.json" % item["序号"])):
        d = json.loads(fp.read_text(encoding="utf-8"))
        if "page" in fp.name:
            continue
        for r in (d.get("results") or []):
            url = real_url(r.get("url") or "")
            if not url.startswith("http"):
                continue
            if any(s in url for s in SKIP):
                continue
            blob = (r.get("title") or "") + " " + (r.get("snippet") or "")
            c = coverage(names, blob)[0]
            pref = next((i for i, k in enumerate(PREFER) if k in url), 99)
            cands.append((c, -pref, url))
    cands.sort(reverse=True)
    return cands[0][2] if cands else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--outdir", default=str(NET))
    ap.add_argument("--sample", default=str(SAMPLE))
    ap.add_argument("--reg", default=str(REG))
    a = ap.parse_args()
    net = Path(a.outdir)
    reg_p = Path(a.reg)
    items = json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]
    reg = {}
    if reg_p.exists():
        reg = json.loads(reg_p.read_text(encoding="utf-8"))
    n_ok = n_no = 0
    for x in items:
        if not (a.start <= x["序号"] < a.start + a.limit):
            continue
        fp = net / ("%03d_%s.top.txt" % (x["序号"], re.sub(r"[^\w\u4e00-\u9fff]", "_", x["方名"])))
        if fp.exists():
            n_ok += 1
            continue
        names = ingredients(x["组成"])
        url = pick(x, names)
        if not url:
            reg[str(x["序号"])] = {"url": "", "status": "没有可用的候选页面"}
            n_no += 1
            print("  #%03d %-12s ✘ 没有可用候选" % (x["序号"], x["方名"][:12]))
            continue
        try:
            html = fetch(url, timeout=25)
            t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
            t = strip_tags(t)
            i = t.find(x["方名"])
            txt = t[max(0, i - 200):max(0, i - 200) + 2500] if i >= 0 else t[:2500]
            fp.write_text("URL: %s\n\n%s" % (url, txt), encoding="utf-8")
            reg[str(x["序号"])] = {"url": url, "status": "ok", "chars": len(txt)}
            c, n, h = coverage(names, txt)
            n_ok += 1
            print("  #%03d %-12s ✔ %-40s 正文命中 %d/%d" % (x["序号"], x["方名"][:12],
                                                            url[:40], c, n))
        except Exception as ex:                                  # noqa: BLE001
            reg[str(x["序号"])] = {"url": url, "status": "失败：%s: %s"
                                   % (type(ex).__name__, ex)}
            n_no += 1
            print("  #%03d %-12s ★ %s: %s" % (x["序号"], x["方名"][:12], type(ex).__name__, ex))
        reg_p.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(a.sleep)
    print()
    print("  页面 OK %d ｜ 没拿到 %d" % (n_ok, n_no))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
