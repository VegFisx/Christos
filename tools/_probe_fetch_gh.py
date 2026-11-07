# -*- coding: utf-8 -*-
r"""一次性：从 GitHub API 拉候选文件（中文路径 percent-encode）+ codeload 连通性测试。"""
from __future__ import annotations

import base64
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net")
OUT.mkdir(parents=True, exist_ok=True)


def api(u):
    r = urllib.request.Request(u, headers=UA)
    return json.load(urllib.request.urlopen(r, timeout=30))


def fetch(full, path, save):
    u = "https://api.github.com/repos/%s/contents/%s" % (full, urllib.parse.quote(path))
    d = api(u)
    blob = base64.b64decode(d["content"])
    (OUT / save).write_bytes(blob)
    return blob


def main() -> int:
    # 已存过的 data.json 先看结构
    p = OUT / "data.json"
    if p.exists():
        b = p.read_bytes()
        print("== PharmaScanAI data.json (%d bytes) 头部 ==" % len(b))
        print(b[:400].decode("utf-8", "replace"))
        print()

    # 药典 2025 目录 CSV
    b2 = fetch("cutcutjust/PharmaScanAI-v2-final",
               "Pharmacopoeia/中国药典2025年版1-4部目录.csv", "chp2025_toc.csv")
    print("== chp2025_toc.csv (%d bytes) 头部 ==" % len(b2))
    print(b2[:500].decode("utf-8-sig", "replace"))
    print()

    # chp_search_2020：看它的数据来源
    for src, save in (("provider/chinese_pharmacopoeia.py", "chp_provider.py"),
                      ("tools/chp_search.py", "chp_tool.py")):
        b = fetch("feiwangoooh/chp_search_2020", src, save)
        print("== %s (%d bytes) ==" % (save, len(b)))
        print(b[:1000].decode("utf-8", "replace"))
        print()

    # codeload 连通性（Range 取头 2 KB）
    for full, br in (("cutcutjust/KnowledgeGraph", "main"), ("flyrae/PPRC", "main")):
        u = "https://codeload.github.com/%s/zip/refs/heads/%s" % (full, br)
        try:
            req = urllib.request.Request(u, headers=dict(UA, Range="bytes=0-2000"))
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read(2001)
                print("codeload OK  %-26s status=%s got=%d ct=%s"
                      % (full, r.status, len(data), r.headers.get("Content-Type")))
        except Exception as ex:
            print("codeload ERR %-26s %s" % (full, str(ex)[:110]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
