# -*- coding: utf-8 -*-
r"""一次性探针：核查"药典/对照品"类公开数据源的可访问性（为判据试点探路）。

只做**轻量可达性检查**：每个 URL 发 1 次请求（15 s 超时），报告 状态码/类型/大小/标题片段。
不发任何写操作、不抓全量、不登录。跑法：python tools\_probe_net_yaodian.py（需联网）。
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

URLS = [
    ("GitHub 仓库搜索：中国药典",
     "https://api.github.com/search/repositories?q=" + urllib.parse.quote("中国药典") + "&per_page=5"),
    ("GitHub 仓库搜索：chinese pharmacopoeia",
     "https://api.github.com/search/repositories?q=pharmacopoeia+chinese&per_page=5"),
    ("国家药监局 NMPA 主站", "https://www.nmpa.gov.cn/"),
    ("中检院 NIFDC 主站（标准物质）", "https://www.nifdc.org.cn/nifdc/"),
    ("HERB 数据库主站（现有数据源）", "http://herb.ac.cn/"),
    ("蒲公英（药品标准社区）", "https://www.ouryao.com/"),
]


def probe(name: str, url: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read(20000)
            ctype = r.headers.get("Content-Type", "")
            note = ""
            if "json" in ctype:
                try:
                    d = json.loads(body.decode("utf-8", "replace"))
                    items = d.get("items")
                    if items is not None:
                        note = " | 命中 %d 个仓库：" % d.get("total_count", 0) + \
                               "; ".join("%s(★%s)" % (it.get("full_name"), it.get("stargazers_count"))
                                         for it in items[:5])
                except Exception:
                    note = ""
            print("OK  %-28s %s [%s] %d bytes%s"
                  % (name, r.status, ctype.split(";")[0], len(body), note))
    except Exception as ex:
        print("ERR %-28s %s: %s" % (name, type(ex).__name__, str(ex)[:120]))


def main() -> int:
    print("== 药典/对照品数据源可达性（每站 1 次请求） ==")
    for name, url in URLS:
        probe(name, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
