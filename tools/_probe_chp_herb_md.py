# -*- coding: utf-8 -*-
"""一次性探针：药典「药材和饮片」条目的正文长什么样（找【来源】拉丁学名）。"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

Z = Path(r"D:\ProgramData\DSHNS\chemreact-staging\reports\_probe_net\indkb.zip")
SUB = "一部/药材和饮片/"


def main() -> None:
    z = zipfile.ZipFile(Z)
    md = [i.filename for i in z.infolist() if i.filename.endswith(".md") and SUB in i.filename]
    print("药材和饮片 md =", len(md))
    for want in ("生地黄", "蓝布正", "杠板归"):
        fn = next((n for n in md if Path(n).stem == want), None)
        print("=" * 90)
        if not fn:
            print("%s：没有这个文件" % want)
            continue
        t = z.read(fn).decode("utf-8", "replace")
        print("%s  【文件 %s，%d 字符】" % (want, Path(fn).stem, len(t)))
        body = t.split("---", 2)[-1]
        body = re.sub(r"\s+", " ", body)
        p = body.find("【来源】")
        print("   有【来源】= %s" % (p >= 0))
        if p >= 0:
            print("   来源段：", body[p:p + 320])
        else:
            print("   正文前 300 字：", body[:300])
        # 拉丁学名扫描（全篇）
        lat = re.findall(r"\b([A-Z][a-z]{3,})\s+([a-z]{4,})\b", body)
        print("   全文拉丁双名候选：", lat[:6])


if __name__ == "__main__":
    main()
