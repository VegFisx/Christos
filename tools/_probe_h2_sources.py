# -*- coding: utf-8 -*-
r"""一次性探针：H2 逐条核对走哪条信道？（只发少量请求）"""
from __future__ import annotations

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
from h2_fetch import fetch, strip_tags                     # noqa: E402

NAMES = ["五苓散", "补中益气汤"]
# 用 {q} 占位（模板里本来就有 %3A 这类转义，用 % 格式化会炸）
TARGETS = [
    ("Bing", "https://www.bing.com/search?setlang=zh-CN&q={q}"),
    ("搜狗", "https://www.sogou.com/web?query={q}"),
    ("360搜索", "https://www.so.com/s?q={q}"),
    ("中医世家", "https://www.zysj.com.cn/index/search?keyword={q}"),
    ("中医世家http", "http://www.zysj.com.cn/index/search?keyword={q}"),
    ("医学百科", "https://www.yixue.com/index.php?search={q}"),
    ("中药大全", "http://www.zhongyoo.com/search.php?keyword={q}"),
    ("A+医学百科", "http://www.a-hospital.com/w/{q}"),
    ("维基文库搜索", "https://zh.wikisource.org/w/index.php?search={q}"),
    ("维基百科", "https://zh.wikipedia.org/wiki/{q}"),
    ("中国哲学书", "https://ctext.org/searchbooks.pl?if=gb&searchu={q}"),
]


def main() -> None:
    for label, tmpl in TARGETS:
        for nm in (NAMES if label in ("Bing",) else NAMES[:1]):
            q = urllib.parse.quote(nm + (" 组成" if label in ("Bing", "搜狗", "360搜索") else ""))
            url = tmpl.replace("{q}", q)
            t0 = time.time()
            try:
                html = fetch(url, timeout=25)
                txt = strip_tags(html)
                hit = nm in html
                comp = any(k in txt for k in ("组成", "处方", "方药", "配方"))
                print("  %-12s %-8s HTTP OK ｜ %6d 字节 ｜ 用时 %.1fs ｜ 含方名=%s ｜ 含组成字样=%s"
                      % (label, nm, len(html), time.time() - t0, hit, comp))
                print("      首 120 字：%s" % txt[:120])
            except Exception as ex:                            # noqa: BLE001
                print("  %-12s %-8s ★ %s: %s" % (label, nm, type(ex).__name__, ex))
            time.sleep(2.5)


if __name__ == "__main__":
    main()
