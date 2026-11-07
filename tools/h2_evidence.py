# -*- coding: utf-8 -*-
r"""H2 · 紧凑证据表：每条一行证据，供**逐条阅读定档**。

对第 n 条，给出：
  · 库里组成（截断）与拆出的药材
  · **最佳证据**（取"命中药材数最多"的那条来源；页面正文优先于摘要）
  · 该来源的 URL 与文本片段

用法：``python tools\h2_evidence.py --start 1 --limit 50``
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

STAGE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STAGE / "tools"))
from h2_judge_sheet import ingredients, coverage    # noqa: E402
from h2_fetch_top import real_url                   # noqa: E402

NET = STAGE / "reports" / "_h2_net"
SAMPLE = STAGE / "data" / "h2_sample.json"


def evidence_for(x: dict, net: Path = NET) -> dict:
    names = ingredients(x["组成"])
    best = {"cov": -1, "text": "", "url": "", "kind": ""}
    for fp in sorted(net.glob("%03d_*.json" % x["序号"])):
        d = json.loads(fp.read_text(encoding="utf-8"))
        if "page" in fp.name:
            pg = d.get("page") or {}
            if pg.get("excerpt"):
                c = coverage(names, pg["excerpt"])[0]
                if c > best["cov"] or (c == best["cov"] and best["kind"] != "page"):
                    best = {"cov": c, "text": pg["excerpt"], "url": pg.get("url") or "",
                            "kind": "page:" + str(pg.get("site"))}
        else:
            for r in (d.get("results") or []):
                blob = (r.get("title") or "") + " " + (r.get("snippet") or "")
                c = coverage(names, blob)[0]
                if c > best["cov"]:
                    best = {"cov": c, "text": blob, "url": real_url(r.get("url") or ""),
                            "kind": "search:" + str(d.get("engine_used"))}
        tp = fp.with_suffix(".top.txt")
        if tp.exists():
            t = tp.read_text(encoding="utf-8")
            body = t.split("\n\n", 1)[-1]
            c = coverage(names, body)[0]
            if c > best["cov"] or (c == best["cov"] and best["cov"] <= 0 and body):
                best = {"cov": c, "text": body, "url": t.split("\n", 1)[0].replace("URL: ", ""),
                        "kind": "top-page"}
    return {"names": names, "best": best}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--width", type=int, default=210)
    ap.add_argument("--net", default=str(NET))
    ap.add_argument("--sample", default=str(SAMPLE))
    ap.add_argument("--only", default="", help="只打印这些序号（逗号分隔，如 2,5,9）")
    ap.add_argument("--from-screen", action="store_true",
                    help="只打印 data\\h2_screen.json 里 建议=查无 的那些")
    ap.add_argument("--screen", default=str(STAGE / "data" / "h2_screen.json"))
    a = ap.parse_args()
    only = {int(x) for x in a.only.split(",") if x.strip().isdigit()}
    if a.from_screen:
        scr = json.loads(Path(a.screen).read_text(encoding="utf-8"))
        only |= {x["序号"] for x in scr if x["建议"] == "查无"}
    net = Path(a.net)
    items = json.loads(Path(a.sample).read_text(encoding="utf-8"))["items"]
    for x in items:
        if not (a.start <= x["序号"] < a.start + a.limit):
            continue
        if only and x["序号"] not in only:
            continue
        e = evidence_for(x, net)
        b = e["best"]
        txt = re.sub(r"\s+", " ", b["text"])
        txt = re.sub(r"^URL: \S+\s*", "", txt)
        print("#%03d %s ｜ %s" % (x["序号"], x["方名"], x["出处"]))
        print("   库：%s" % re.sub(r"\s+", "", x["组成"])[:88])
        print("   材：%s｜覆盖 %d/%d（%s）"
              % ("、".join(e["names"])[:56], b["cov"], len(e["names"]), b["kind"]))
        print("   证：%s" % txt[:a.width])
        print("   源：%s" % (b["url"] or "（无）")[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
