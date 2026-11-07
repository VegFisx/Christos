# -*- coding: utf-8 -*-
r"""三步页 v0.3 冒烟：自定义输出目录 + 多药材筛选（对 127.0.0.1:8769）。"""
from __future__ import annotations

import json
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

B = "http://127.0.0.1:8769"
CUSTOM = r"D:\ProgramData\DSHNS\chemreact-staging\reports\_custom_out_test"


def get(u):
    with urllib.request.urlopen(u, timeout=30) as r:
        return r.status, r.read()


def run(form):
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(B + "/run", data=data)
    rid = json.loads(urllib.request.urlopen(req, timeout=30).read())["id"]
    for _ in range(150):
        time.sleep(2)
        d = json.loads(get(B + "/status?id=" + rid)[1])
        if d["state"] != "running":
            return rid, d
    return rid, {"state": "timeout"}


def main() -> int:
    box = []
    rid, d = run({"herb": "白芥子", "limit": "4", "rounds": "1", "outdir": CUSTOM})
    print("A) 自定义目录:", d["state"], "report=", d.get("report"))
    st, b = get(B + "/files/" + urllib.parse.quote(d["report"]) + "?rid=" + rid)
    print("   报告经 rid 取回:", st, len(b), "| 自定义目录有文件:",
          len(list(Path(CUSTOM).glob("*"))) > 0)
    box.append(st == 200)
    rid2, d2 = run({"herb": "甘草,黄芪", "limit": "2", "rounds": "1"})
    st2, b2 = get(B + "/files/" + urllib.parse.quote(d2["report"]) + "?rid=" + rid2)
    print("B) 双药材:", d2["state"], "| 报告含药材筛选 hsel:", b"hsel" in b2)
    box.append(st2 == 200 and b"hsel" in b2)
    print("== 汇总:", box, "==")
    return 0 if all(box) else 1


if __name__ == "__main__":
    sys.exit(main())
