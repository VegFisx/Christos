# -*- coding: utf-8 -*-
# 一次性：解析联网抓到的核查材料（PaRoutes 仓库 / figshare 许可 / COCONUT 许可 / AiZynthFinder 过滤段）
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

P = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\paper\probe")

try:
    s = json.loads((P / "paroutes_search2.json").read_text(encoding="utf-8"))
    for it in s.get("items", [])[:5]:
        print("PaRoutes候选:", it["full_name"], "| stars", it["stargazers_count"],
              "|", (it.get("description") or "")[:70])
except Exception as ex:
    print("paroutes parse fail:", ex)

try:
    fs = json.loads((P / "figshare_5104873.json").read_text(encoding="utf-8"))
    lic = fs.get("license") or {}
    print("figshare license:", lic.get("name"), "|", str(lic)[:120])
except Exception as ex:
    print("figshare fail:", ex)

try:
    h = (P / "coconut_home.html").read_text(encoding="utf-8", errors="replace")
    hits = set()
    for m in re.findall(r"[^<>{}]{0,60}(?:CC[- ]BY|licen[cs]e|Creative Commons)[^<>{}]{0,90}",
                        h, re.I):
        m = " ".join(m.split())
        if len(m) > 12:
            hits.add(m[:150])
    for x in list(hits)[:6]:
        print("COCONUT主页:", x)
    if not hits:
        print("COCONUT主页: 未找到许可关键词（需另查）")
except Exception as ex:
    print("coconut fail:", ex)

try:
    h = (P / "aizynthfinder_paper.html").read_text(encoding="utf-8", errors="replace")
    txt = " ".join(re.sub(r"<[^>]+>", " ", h).split())
    seen = set()
    for m in list(re.finditer(r"filter", txt, re.I))[:20]:
        i = m.start()
        seg = txt[max(0, i - 170):i + 260]
        key = seg[:60]
        if key in seen:
            continue
        seen.add(key)
        print("---", seg[:380])
except Exception as ex:
    print("aizynth fail:", ex)
