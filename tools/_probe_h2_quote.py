# -*- coding: utf-8 -*-
r"""一次性探针：方名**加引号**再查，命中率会不会明显变好？（2 次请求）"""
from __future__ import annotations

import sys
import time
import urllib.parse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, r"D:\ProgramData\DSHNS\chemreact-staging\tools")
from h2_fetch import fetch, parse_bing                     # noqa: E402

for q in ("七制香附丸 组成", '"七制香附丸" 组成'):
    url = "https://cn.bing.com/search?mkt=zh-CN&setlang=zh-CN&q=" + urllib.parse.quote(q)
    try:
        html = fetch(url, timeout=20)
        rs = parse_bing(html)
        print("== 查询：%s → %d 条" % (q, len(rs)))
        for r in rs[:3]:
            print("   T: %s" % r["title"][:56])
            print("   S: %s" % (r["snippet"] or "")[:100])
    except Exception as ex:                                # noqa: BLE001
        print("== 查询：%s ★ %s: %s" % (q, type(ex).__name__, ex))
    time.sleep(2)
