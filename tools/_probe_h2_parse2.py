# -*- coding: utf-8 -*-
r"""一次性探针：第二批的 360 / 搜狗 页面结构是不是变了？（各发 1 次请求）"""
from __future__ import annotations

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
from h2_fetch import fetch, strip_tags, parse_bing         # noqa: E402

Q = "二陈汤 组成"
URLS = [
    ("360", "https://www.so.com/s?q=%s" % urllib.parse.quote(Q)),
    ("搜狗", "https://www.sogou.com/web?query=%s" % urllib.parse.quote(Q)),
    ("Bing", "https://cn.bing.com/search?mkt=zh-CN&q=%s" % urllib.parse.quote(Q)),
]

for name, url in URLS:
    try:
        html = fetch(url, timeout=25)
    except Exception as ex:                                # noqa: BLE001
        print("  %-5s ★ %s: %s" % (name, type(ex).__name__, ex))
        time.sleep(2)
        continue
    print("  %-5s %d 字节 ｜ 含结果类名：res-list=%d b_algo=%d vrwrap=%d ｜ 含验证=%d"
          % (name, len(html),
             html.count("res-list"), html.count("b_algo"), html.count("vrwrap"),
             html.count("验证")))
    txt = strip_tags(html)
    print("       正文前 200 字：%s" % re.sub(r"\s+", " ", txt)[:200])
    # 打印所有 <h3> 里的锚点（不同站点标题都在 h3）
    hits = re.findall(r"<h3[^>]*>.{0,200}?<a[^>]+href=\"([^\"]+)\"[^>]*>(.{0,80}?)</a>", html, re.S)
    print("       h3 锚点 %d 个，前 3 个：" % len(hits))
    for u, t in hits[:3]:
        print("         %-60s %s" % (u[:60], strip_tags(t)[:40]))
    time.sleep(2.5)

print()
print("== Bing 解析测试（二陈汤）==")
try:
    html = fetch("https://cn.bing.com/search?mkt=zh-CN&setlang=zh-CN&q=%s"
                 % urllib.parse.quote("二陈汤 组成"), timeout=25)
    rs = parse_bing(html)
    print("  解析出 %d 条：" % len(rs))
    for r in rs[:5]:
        print("   - %-44s %s" % (r["title"][:44], (r["snippet"] or "")[:80]))
except Exception as ex:                                    # noqa: BLE001
    print("  ★ %s: %s" % (type(ex).__name__, ex))
