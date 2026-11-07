# -*- coding: utf-8 -*-
r"""一次性：下载两个候选仓库 zip（codeload）并列出内部结构（判据试点探路）。"""
from __future__ import annotations

import sys
import urllib.request
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
OUT = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net")
OUT.mkdir(parents=True, exist_ok=True)
JOBS = [("cutcutjust/KnowledgeGraph", "main", "kg.zip"),
        ("flyrae/PPRC", "main", "pprc.zip")]


def download(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers=UA)
    tmp = dst.with_suffix(dst.suffix + ".part")
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            total += len(chunk)
            if total % (10 << 20) < (1 << 20):
                print("   ... %s %.1f MB" % (dst.name, total / 1048576), flush=True)
    tmp.replace(dst)
    print("   下载完成 %s：%.1f MB" % (dst.name, dst.stat().st_size / 1048576))


def main() -> int:
    for full, br, name in JOBS:
        dst = OUT / name
        if not dst.exists() or dst.stat().st_size < 1000:
            print("下载 %s ..." % full)
            download("https://codeload.github.com/%s/zip/refs/heads/%s" % (full, br), dst)
        z = zipfile.ZipFile(dst)
        names = z.namelist()
        print("==== %s：%d 个条目 ====" % (name, len(names)))
        for n in names[:40]:
            info = z.getinfo(n)
            print("   %9d  %s" % (info.file_size, n))
        # 大文件（可用的药典正文）前 20 个
        big = sorted((z.getinfo(n) for n in names), key=lambda i: -i.file_size)[:15]
        print("   -- 最大的 15 个 --")
        for info in big:
            print("   %9.1f KB  %s" % (info.file_size / 1024, info.filename))
    return 0


if __name__ == "__main__":
    sys.exit(main())
