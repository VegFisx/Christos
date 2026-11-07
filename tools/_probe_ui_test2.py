# -*- coding: utf-8 -*-
r"""三步页 v0.2 冒烟：routes 任务 + predict 回归（对 127.0.0.1:8768）。"""
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

B = "http://127.0.0.1:8768"


def get(u):
    with urllib.request.urlopen(u, timeout=30) as r:
        return r.status, r.read()


def run(form):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(B + "/run", data=data)
    j = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print("  POST ->", j)
    rid = j.get("id")
    for _ in range(150):
        time.sleep(2)
        d = json.loads(get(B + "/status?id=" + rid)[1])
        if d["state"] != "running":
            print("  state=%s seconds=%.0f report=%s" % (d["state"], d["seconds"], d.get("report")))
            if d.get("report"):
                st, b = get(B + "/files/" + urllib.parse.quote(d["report"]))
                print("  GET report -> %s %d bytes" % (st, len(b)))
            return d["state"] == "done"
    return False


def main() -> int:
    st, body = get(B + "/")
    print("GET / ->", st, len(body), "找路线" in body.decode("utf-8"))
    print("== routes 任务（阿司匹林 深度1） ==")
    ok1 = run({"kind": "routes", "target": "CC(=O)Oc1ccccc1C(=O)O", "depth": "1", "show": "1"})
    print("== predict 回归（白芥子 4 成分） ==")
    ok2 = run({"herb": "白芥子", "limit": "4", "rounds": "1"})
    print("== 汇总：routes=%s predict=%s ==" % (ok1, ok2))
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
