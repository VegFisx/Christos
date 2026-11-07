# -*- coding: utf-8 -*-
r"""一次性：对本地三步页服务器做冒烟测试（GET / -> POST /run -> 轮询 -> 取报告）。"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

B = "http://127.0.0.1:8766"


def get(u):
    with urllib.request.urlopen(u, timeout=30) as r:
        return r.status, r.read()


def main() -> int:
    st, body = get(B + "/")
    print("GET / -> %s %d bytes · 三步页在: %s" % (st, len(body), "第 1 步" in body.decode("utf-8")))
    data = urllib.parse.urlencode({"herb": "白芥子", "limit": "6", "rounds": "1"}).encode()
    req = urllib.request.Request(B + "/run", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        j = json.loads(r.read())
    print("POST /run ->", j)
    rid = j.get("id")
    if not rid:
        return 1
    for i in range(150):
        time.sleep(2)
        _, body = get(B + "/status?id=" + rid)
        d = json.loads(body)
        print("  poll %-3d state=%-7s seconds=%.0f" % (i, d.get("state"), d.get("seconds", 0)))
        if d.get("state") != "running":
            print("  report=%s csv=%s" % (d.get("report"), d.get("csv")))
            if d.get("report"):
                st2, body2 = get(B + "/files/" + urllib.parse.quote(d["report"]))
                print("GET /files/report -> %s %d bytes" % (st2, len(body2)))
            sel = (d.get("meta") or {}).get("selection") or {}
            print("  meta.selection:", json.dumps(sel, ensure_ascii=False)[:220])
            print("  tail 末尾:", (d.get("tail") or "").strip().splitlines()[-1][:120])
            return 0 if d.get("state") == "done" else 2
    print("超时未完成")
    return 3


if __name__ == "__main__":
    sys.exit(main())
