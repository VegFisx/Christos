# -*- coding: utf-8 -*-
"""一次性探针：indkb.zip 里到底有什么，含不含"成方制剂"的【处方】。

只回答一个问题：**能不能纯离线从药典拿到方剂组成**。
"""
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
KEYS = ("六味地黄丸", "藿香正气水", "桂枝茯苓丸", "复方丹参滴丸")


def main() -> None:
    z = zipfile.ZipFile(Z)
    infos = z.infolist()
    print("zip 条目 = %d，解压合计 %.1f MB"
          % (len(infos), sum(i.file_size for i in infos) / 1048576))
    print("条目样例（前 15）：")
    for i in infos[:15]:
        print("   %-60s %8.1f KB" % (i.filename[:60], i.file_size / 1024))
    # 扩展名分布
    ext = {}
    for i in infos:
        e = Path(i.filename).suffix.lower() or "(无)"
        ext[e] = ext.get(e, 0) + 1
    print("扩展名分布：", sorted(ext.items(), key=lambda t: -t[1])[:10])

    # 在文本类条目里搜关键词
    hits = {k: [] for k in KEYS}
    txt_entries = [i for i in infos
                   if Path(i.filename).suffix.lower() in (".txt", ".json", ".jsonl",
                                                          ".md", ".csv", ".html", ".xml")]
    print("\n文本类条目 = %d，逐个搜索关键词……" % len(txt_entries))
    for i in txt_entries:
        try:
            raw = z.read(i.filename)
        except Exception as ex:                            # noqa: BLE001
            print("   [warn] 读 %s 失败：%s" % (i.filename, ex))
            continue
        try:
            text = raw.decode("utf-8", "replace")
        except Exception:                                  # noqa: BLE001
            continue
        for k in KEYS:
            p = text.find(k)
            if p >= 0 and len(hits[k]) < 2:
                seg = re.sub(r"\s+", " ", text[max(0, p - 80): p + 300])
                hits[k].append((i.filename, seg))
    for k, v in hits.items():
        print("\n=== %s ===" % k)
        if not v:
            print("   未找到")
            continue
        for fn, seg in v:
            print("   [%s] …%s…" % (fn, seg))


if __name__ == "__main__":
    main()
